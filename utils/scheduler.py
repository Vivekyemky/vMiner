"""
Background scheduler for periodic vCenter synchronization.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from backend.db_manager import DatabaseManager
from backend.sync_engine import SyncEngine
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SyncScheduler:
    """Manages periodic synchronization of vCenter inventory."""
    
    def __init__(self, sync_interval_minutes: int = 60):
        self.sync_interval_minutes = sync_interval_minutes
        self.scheduler = BackgroundScheduler()
        
        # Initialize components
        self.db_manager = DatabaseManager(
            local_db_path="inventory.db",
            sql_connection_string=os.getenv("SQL_CONNECTION_STRING")
        )
        self.sync_engine = SyncEngine(self.db_manager, max_workers=10)
    
    def start(self):
        """Start the scheduler."""
        logger.info(f"Starting sync scheduler with interval: {self.sync_interval_minutes} minutes")
        
        # Schedule periodic sync
        self.scheduler.add_job(
            self.sync_engine.sync_all_vcenters,
            'interval',
            minutes=self.sync_interval_minutes,
            id='vcenter_sync',
            replace_existing=True
        )
        
        # Run initial sync
        logger.info("Running initial sync...")
        self.sync_engine.sync_all_vcenters()
        
        self.scheduler.start()
        logger.info("Scheduler started successfully")
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
    
    def update_interval(self, new_interval_minutes: int):
        """Update sync interval."""
        self.sync_interval_minutes = new_interval_minutes
        self.scheduler.reschedule_job(
            'vcenter_sync',
            trigger='interval',
            minutes=new_interval_minutes
        )
        logger.info(f"Sync interval updated to {new_interval_minutes} minutes")

# Global scheduler instance
scheduler = None

def get_scheduler(sync_interval_minutes: int = 60):
    """Get or create scheduler instance."""
    global scheduler
    if scheduler is None:
        scheduler = SyncScheduler(sync_interval_minutes)
    return scheduler
