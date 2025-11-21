"""vMiner - Enterprise vCenter Inventory Management Platform

A production-ready REST API for intelligent vCenter inventory management
and natural language querying across distributed VMware environments.

Author: Vivek Yemky <vivek.yemky@gmail.com>
License: MIT
"""

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime, timedelta
import jwt
import os
from backend.db_manager import DatabaseManager
from backend.sync_engine import SyncEngine
from backend.query_engine import QueryEngine
from utils.export_utils import ExportUtils
from utils.scheduler import get_scheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="vMiner API",
    description="Enterprise vCenter Inventory Management API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
ALGORITHM = "HS256"

# Initialize components
db_manager = DatabaseManager(
    local_db_path="inventory.db",
    sql_connection_string=os.getenv("SQL_CONNECTION_STRING")
)
db_manager.init_local_db()

sync_engine = SyncEngine(db_manager, max_workers=10)
query_engine = QueryEngine(db_manager)
export_utils = ExportUtils()

# Initialize scheduler (will start on app startup)
sync_scheduler = None

@app.on_event("startup")
async def startup_event():
    """Initialize scheduler on startup."""
    global sync_scheduler
    sync_interval = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))
    sync_scheduler = get_scheduler(sync_interval)
    # Uncomment to enable automatic syncing on startup
    # sync_scheduler.start()
    logger.info("Application started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    if sync_scheduler:
        try:
            sync_scheduler.stop()
        except Exception as e:
            logger.warning(f"Scheduler stop failed (may not be running): {e}")
    logger.info("Application shutdown")

# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ChatQueryRequest(BaseModel):
    query: str
    mode: str = "cached"  # cached or live

class ChatQueryResponse(BaseModel):
    query: str
    corrected_query: Optional[str] = None
    results: Dict[str, Any]
    execution_time: float

class SyncRequest(BaseModel):
    vcenter_ids: Optional[List[int]] = None  # If None, sync all

class ExportRequest(BaseModel):
    query: str
    format: str = "csv"  # csv, json, excel

# Helper functions
def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=24)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# Routes

@app.get("/")
async def root():
    return {
        "message": "vMiner API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token."""
    # TODO: Implement actual authentication against your user database
    # For now, simple validation
    if request.username and request.password:
        access_token = create_access_token(data={"sub": request.username})
        return LoginResponse(access_token=access_token)
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/auth/logout")
async def logout(username: str = Depends(verify_token)):
    """Logout user (client should discard token)."""
    return {"message": "Logged out successfully"}

@app.get("/api/vcenters")
async def get_vcenters(username: str = Depends(verify_token)):
    """Get list of all vCenters."""
    from backend.db_manager import VCenter
    session = db_manager.get_local_session()
    vcenters = session.query(VCenter).all()
    session.close()
    
    return {
        "vcenters": [
            {
                "id": vc.id,
                "hostname": vc.hostname,
                "is_active": vc.is_active,
                "last_sync": vc.last_sync.isoformat() if vc.last_sync else None,
                "sync_status": vc.sync_status
            }
            for vc in vcenters
        ]
    }

@app.post("/api/vcenters/sync")
async def sync_vcenters(
    background_tasks: BackgroundTasks,
    request: SyncRequest,
    username: str = Depends(verify_token)
):
    """Trigger vCenter synchronization."""
    if request.vcenter_ids:
        # Sync specific vCenters
        background_tasks.add_task(sync_specific_vcenters, request.vcenter_ids)
        return {"message": f"Sync started for {len(request.vcenter_ids)} vCenters"}
    else:
        # Sync all vCenters
        background_tasks.add_task(sync_engine.sync_all_vcenters)
        return {"message": "Sync started for all vCenters"}

def sync_specific_vcenters(vcenter_ids: List[int]):
    """Background task to sync specific vCenters."""
    for vcenter_id in vcenter_ids:
        try:
            sync_engine.sync_single_vcenter(vcenter_id)
        except Exception as e:
            logger.error(f"Failed to sync vCenter {vcenter_id}: {e}")

@app.get("/api/vcenters/{vcenter_id}/status")
async def get_vcenter_status(vcenter_id: int, username: str = Depends(verify_token)):
    """Get sync status of a specific vCenter."""
    from backend.db_manager import VCenter
    session = db_manager.get_local_session()
    vcenter = session.query(VCenter).filter(VCenter.id == vcenter_id).first()
    session.close()
    
    if not vcenter:
        raise HTTPException(status_code=404, detail="vCenter not found")
    
    return {
        "id": vcenter.id,
        "hostname": vcenter.hostname,
        "sync_status": vcenter.sync_status,
        "last_sync": vcenter.last_sync.isoformat() if vcenter.last_sync else None
    }

@app.post("/api/query/chat", response_model=ChatQueryResponse)
async def chat_query(request: ChatQueryRequest, username: str = Depends(verify_token)):
    """Execute natural language query."""
    start_time = datetime.utcnow()
    
    try:
        results = query_engine.parse_and_execute(request.query)
        
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        return ChatQueryResponse(
            query=request.query,
            results=results,
            execution_time=execution_time
        )
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vms")
async def get_vms(
    power_state: Optional[str] = None,
    cluster: Optional[str] = None,
    host: Optional[str] = None,
    username: str = Depends(verify_token)
):
    """Get list of VMs with optional filters."""
    from backend.db_manager import VirtualMachine
    session = db_manager.get_local_session()
    
    query = session.query(VirtualMachine)
    
    if power_state:
        query = query.filter(VirtualMachine.power_state == power_state)
    if cluster:
        query = query.filter(VirtualMachine.cluster.like(f"%{cluster}%"))
    if host:
        query = query.filter(VirtualMachine.host.like(f"%{host}%"))
    
    vms = query.all()
    session.close()
    
    return {
        "count": len(vms),
        "vms": [query_engine._vm_to_dict(vm) for vm in vms]
    }

@app.get("/api/hosts")
async def get_hosts(
    cluster: Optional[str] = None,
    no_vms: Optional[bool] = None,
    username: str = Depends(verify_token)
):
    """Get list of hosts with optional filters."""
    from backend.db_manager import HostSystem
    session = db_manager.get_local_session()
    
    query = session.query(HostSystem)
    
    if cluster:
        query = query.filter(HostSystem.cluster.like(f"%{cluster}%"))
    if no_vms:
        query = query.filter(HostSystem.vm_count == 0)
    
    hosts = query.all()
    session.close()
    
    return {
        "count": len(hosts),
        "hosts": [query_engine._host_to_dict(host) for host in hosts]
    }

@app.get("/api/datastores")
async def get_datastores(
    empty: Optional[bool] = None,
    username: str = Depends(verify_token)
):
    """Get list of datastores with optional filters."""
    from backend.db_manager import Datastore
    session = db_manager.get_local_session()
    
    query = session.query(Datastore)
    
    if empty:
        query = query.filter(Datastore.vm_count == 0)
    
    datastores = query.all()
    session.close()
    
    return {
        "count": len(datastores),
        "datastores": [query_engine._datastore_to_dict(ds) for ds in datastores]
    }

@app.get("/api/clusters")
async def get_clusters(username: str = Depends(verify_token)):
    """Get list of all clusters."""
    from backend.db_manager import Cluster
    session = db_manager.get_local_session()
    
    clusters = session.query(Cluster).all()
    session.close()
    
    return {
        "count": len(clusters),
        "clusters": [query_engine._cluster_to_dict(cluster) for cluster in clusters]
    }

@app.post("/api/export/{format}")
async def export_data(
    format: str,
    request: ExportRequest,
    username: str = Depends(verify_token)
):
    """Export query results to specified format."""
    try:
        # Execute query
        results = query_engine.parse_and_execute(request.query)
        
        # Export based on format
        if format == "csv":
            file_path = export_utils.export_to_csv(results['data'])
        elif format == "json":
            file_path = export_utils.export_to_json(results['data'])
        elif format == "excel":
            file_path = export_utils.export_to_excel(results['data'])
        else:
            raise HTTPException(status_code=400, detail="Invalid export format")
        
        from fastapi.responses import FileResponse
        return FileResponse(
            file_path,
            media_type='application/octet-stream',
            filename=os.path.basename(file_path)
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats(username: str = Depends(verify_token)):
    """Get overall statistics."""
    from backend.db_manager import VirtualMachine, HostSystem, Datastore, Cluster
    session = db_manager.get_local_session()
    
    stats = {
        "total_vms": session.query(VirtualMachine).count(),
        "powered_on_vms": session.query(VirtualMachine).filter(
            VirtualMachine.power_state == 'poweredOn'
        ).count(),
        "total_hosts": session.query(HostSystem).count(),
        "total_datastores": session.query(Datastore).count(),
        "total_clusters": session.query(Cluster).count(),
    }
    
    session.close()
    return stats

@app.get("/api/settings")
async def get_settings(username: str = Depends(verify_token)):
    """Get current application settings."""
    return {
        "sync_interval_minutes": sync_scheduler.sync_interval_minutes if sync_scheduler else 60,
        "scheduler_running": sync_scheduler.scheduler.running if sync_scheduler else False,
        "database_path": db_manager.local_db_path,
    }

@app.put("/api/settings/sync-interval")
async def update_sync_interval(interval_minutes: int, username: str = Depends(verify_token)):
    """Update the sync interval."""
    if sync_scheduler:
        sync_scheduler.update_interval(interval_minutes)
        return {"message": f"Sync interval updated to {interval_minutes} minutes"}
    raise HTTPException(status_code=500, detail="Scheduler not initialized")

@app.post("/api/settings/scheduler/start")
async def start_scheduler(username: str = Depends(verify_token)):
    """Start the background scheduler."""
    if sync_scheduler:
        sync_scheduler.start()
        return {"message": "Scheduler started"}
    raise HTTPException(status_code=500, detail="Scheduler not initialized")

@app.post("/api/settings/scheduler/stop")
async def stop_scheduler(username: str = Depends(verify_token)):
    """Stop the background scheduler."""
    if sync_scheduler:
        sync_scheduler.stop()
        return {"message": "Scheduler stopped"}
    raise HTTPException(status_code=500, detail="Scheduler not initialized")

# ==================== NEW RESOURCE ENDPOINTS ====================

# Snapshots
@app.get("/api/snapshots")
async def get_snapshots(
    vcenter_id: Optional[int] = None,
    vm_name: Optional[str] = None,
    older_than_days: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get VM snapshots with optional filters."""
    from backend.db_manager import Snapshot
    session = db_manager.get_local_session()
    
    query = session.query(Snapshot)
    
    if vcenter_id:
        query = query.filter(Snapshot.vcenter_id == vcenter_id)
    if vm_name:
        query = query.filter(Snapshot.vm_name.like(f"%{vm_name}%"))
    if older_than_days:
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        query = query.filter(Snapshot.created_date < cutoff_date)
    
    snapshots = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(snapshots),
        "snapshots": [
            {
                "id": s.id,
                "vm_name": s.vm_name,
                "snapshot_name": s.snapshot_name,
                "description": s.description,
                "created_date": s.created_date.isoformat() if s.created_date else None,
                "size_mb": s.size_mb,
                "quiesced": s.quiesced,
            }
            for s in snapshots
        ]
    }

# Resource Pools
@app.get("/api/resource-pools")
async def get_resource_pools(
    vcenter_id: Optional[int] = None,
    cluster_moid: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get resource pools with optional filters."""
    from backend.db_manager import ResourcePool
    session = db_manager.get_local_session()
    
    query = session.query(ResourcePool)
    
    if vcenter_id:
        query = query.filter(ResourcePool.vcenter_id == vcenter_id)
    if cluster_moid:
        query = query.filter(ResourcePool.cluster_moid == cluster_moid)
    
    resource_pools = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(resource_pools),
        "resource_pools": [
            {
                "id": rp.id,
                "name": rp.name,
                "cpu_reservation": rp.cpu_reservation,
                "cpu_limit": rp.cpu_limit,
                "memory_reservation": rp.memory_reservation,
                "memory_limit": rp.memory_limit,
                "vm_count": rp.vm_count,
            }
            for rp in resource_pools
        ]
    }

# Port Groups
@app.get("/api/port-groups")
async def get_port_groups(
    vcenter_id: Optional[int] = None,
    vlan_id: Optional[int] = None,
    is_distributed: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get port groups with optional filters."""
    from backend.db_manager import PortGroup
    session = db_manager.get_local_session()
    
    query = session.query(PortGroup)
    
    if vcenter_id:
        query = query.filter(PortGroup.vcenter_id == vcenter_id)
    if vlan_id is not None:
        query = query.filter(PortGroup.vlan_id == vlan_id)
    if is_distributed is not None:
        query = query.filter(PortGroup.is_distributed == is_distributed)
    
    port_groups = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(port_groups),
        "port_groups": [
            {
                "id": pg.id,
                "name": pg.name,
                "vlan_id": pg.vlan_id,
                "is_distributed": pg.is_distributed,
                "vswitch_name": pg.vswitch_name,
                "vm_count": pg.vm_count,
            }
            for pg in port_groups
        ]
    }

# Distributed vSwitches
@app.get("/api/dvs")
async def get_dvs(
    vcenter_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get Distributed Virtual Switches."""
    from backend.db_manager import DistributedVirtualSwitch
    session = db_manager.get_local_session()
    
    query = session.query(DistributedVirtualSwitch)
    
    if vcenter_id:
        query = query.filter(DistributedVirtualSwitch.vcenter_id == vcenter_id)
    
    dvs_list = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(dvs_list),
        "dvs": [
            {
                "id": d.id,
                "name": d.name,
                "version": d.version,
                "num_ports": d.num_ports,
                "num_uplinks": d.num_uplinks,
                "network_io_control_enabled": d.network_io_control_enabled,
            }
            for d in dvs_list
        ]
    }

# VM Templates
@app.get("/api/templates")
async def get_templates(
    vcenter_id: Optional[int] = None,
    guest_os: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get VM templates."""
    from backend.db_manager import VMTemplate
    session = db_manager.get_local_session()
    
    query = session.query(VMTemplate)
    
    if vcenter_id:
        query = query.filter(VMTemplate.vcenter_id == vcenter_id)
    if guest_os:
        query = query.filter(VMTemplate.guest_os.like(f"%{guest_os}%"))
    
    templates = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(templates),
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "guest_os": t.guest_os,
                "cpu_count": t.cpu_count,
                "memory_mb": t.memory_mb,
                "num_disks": t.num_disks,
            }
            for t in templates
        ]
    }

# Storage Adapters
@app.get("/api/storage-adapters")
async def get_storage_adapters(
    vcenter_id: Optional[int] = None,
    host_moid: Optional[str] = None,
    adapter_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get storage adapters."""
    from backend.db_manager import StorageAdapter
    session = db_manager.get_local_session()
    
    query = session.query(StorageAdapter)
    
    if vcenter_id:
        query = query.filter(StorageAdapter.vcenter_id == vcenter_id)
    if host_moid:
        query = query.filter(StorageAdapter.host_moid == host_moid)
    if adapter_type:
        query = query.filter(StorageAdapter.adapter_type.like(f"%{adapter_type}%"))
    
    adapters = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(adapters),
        "storage_adapters": [
            {
                "id": a.id,
                "device": a.device,
                "adapter_type": a.adapter_type,
                "model": a.model,
                "driver": a.driver,
                "status": a.status,
            }
            for a in adapters
        ]
    }

# SCSI LUNs
@app.get("/api/scsi-luns")
async def get_scsi_luns(
    vcenter_id: Optional[int] = None,
    host_moid: Optional[str] = None,
    vendor: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get SCSI LUNs."""
    from backend.db_manager import ScsiLun
    session = db_manager.get_local_session()
    
    query = session.query(ScsiLun)
    
    if vcenter_id:
        query = query.filter(ScsiLun.vcenter_id == vcenter_id)
    if host_moid:
        query = query.filter(ScsiLun.host_moid == host_moid)
    if vendor:
        query = query.filter(ScsiLun.vendor.like(f"%{vendor}%"))
    
    luns = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(luns),
        "scsi_luns": [
            {
                "id": l.id,
                "canonical_name": l.canonical_name,
                "display_name": l.display_name,
                "vendor": l.vendor,
                "model": l.model,
                "capacity_mb": l.capacity_mb,
                "multipath_policy": l.multipath_policy,
                "path_count": l.path_count,
            }
            for l in luns
        ]
    }

# DRS Rules
@app.get("/api/drs-rules")
async def get_drs_rules(
    vcenter_id: Optional[int] = None,
    cluster_moid: Optional[str] = None,
    rule_type: Optional[str] = None,
    enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get DRS rules."""
    from backend.db_manager import DRSRule
    session = db_manager.get_local_session()
    
    query = session.query(DRSRule)
    
    if vcenter_id:
        query = query.filter(DRSRule.vcenter_id == vcenter_id)
    if cluster_moid:
        query = query.filter(DRSRule.cluster_moid == cluster_moid)
    if rule_type:
        query = query.filter(DRSRule.rule_type == rule_type)
    if enabled is not None:
        query = query.filter(DRSRule.enabled == enabled)
    
    rules = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(rules),
        "drs_rules": [
            {
                "id": r.id,
                "rule_name": r.rule_name,
                "rule_type": r.rule_type,
                "enabled": r.enabled,
                "mandatory": r.mandatory,
            }
            for r in rules
        ]
    }

# VM Performance
@app.get("/api/performance/vms")
async def get_vm_performance(
    vcenter_id: Optional[int] = None,
    vm_moid: Optional[str] = None,
    hours: int = 1,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get VM performance metrics."""
    from backend.db_manager import VMPerformance
    session = db_manager.get_local_session()
    
    query = session.query(VMPerformance)
    
    if vcenter_id:
        query = query.filter(VMPerformance.vcenter_id == vcenter_id)
    if vm_moid:
        query = query.filter(VMPerformance.vm_moid == vm_moid)
    
    # Filter by time range
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    query = query.filter(VMPerformance.timestamp >= cutoff_time)
    query = query.order_by(VMPerformance.timestamp.desc())
    
    perf_data = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(perf_data),
        "performance_data": [
            {
                "vm_moid": p.vm_moid,
                "timestamp": p.timestamp.isoformat() if p.timestamp else None,
                "cpu_usage_mhz": p.cpu_usage_mhz,
                "cpu_usage_percent": p.cpu_usage_percent,
                "memory_usage_mb": p.memory_usage_mb,
                "memory_active_mb": p.memory_active_mb,
            }
            for p in perf_data
        ]
    }

# Host Performance
@app.get("/api/performance/hosts")
async def get_host_performance(
    vcenter_id: Optional[int] = None,
    host_moid: Optional[str] = None,
    hours: int = 1,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get host performance metrics."""
    from backend.db_manager import HostPerformance
    session = db_manager.get_local_session()
    
    query = session.query(HostPerformance)
    
    if vcenter_id:
        query = query.filter(HostPerformance.vcenter_id == vcenter_id)
    if host_moid:
        query = query.filter(HostPerformance.host_moid == host_moid)
    
    # Filter by time range
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    query = query.filter(HostPerformance.timestamp >= cutoff_time)
    query = query.order_by(HostPerformance.timestamp.desc())
    
    perf_data = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(perf_data),
        "performance_data": [
            {
                "host_moid": p.host_moid,
                "timestamp": p.timestamp.isoformat() if p.timestamp else None,
                "cpu_usage_mhz": p.cpu_usage_mhz,
                "cpu_usage_percent": p.cpu_usage_percent,
                "memory_usage_mb": p.memory_usage_mb,
            }
            for p in perf_data
        ]
    }

# Events
@app.get("/api/events")
async def get_events(
    vcenter_id: Optional[int] = None,
    severity: Optional[str] = None,
    hours: int = 24,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get vCenter events."""
    from backend.db_manager import Event
    session = db_manager.get_local_session()
    
    query = session.query(Event)
    
    if vcenter_id:
        query = query.filter(Event.vcenter_id == vcenter_id)
    if severity:
        query = query.filter(Event.severity == severity)
    
    # Filter by time range
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    query = query.filter(Event.timestamp >= cutoff_time)
    query = query.order_by(Event.timestamp.desc())
    
    events = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "user_name": e.user_name,
                "entity_name": e.entity_name,
                "message": e.message,
            }
            for e in events
        ]
    }

# Alarms
@app.get("/api/alarms")
async def get_alarms(
    vcenter_id: Optional[int] = None,
    status: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get triggered alarms."""
    from backend.db_manager import Alarm
    session = db_manager.get_local_session()
    
    query = session.query(Alarm)
    
    if vcenter_id:
        query = query.filter(Alarm.vcenter_id == vcenter_id)
    if status:
        query = query.filter(Alarm.status == status)
    if acknowledged is not None:
        query = query.filter(Alarm.acknowledged == acknowledged)
    
    query = query.order_by(Alarm.triggered_time.desc())
    
    alarms = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(alarms),
        "alarms": [
            {
                "id": a.id,
                "alarm_name": a.alarm_name,
                "entity_name": a.entity_name,
                "status": a.status,
                "triggered_time": a.triggered_time.isoformat() if a.triggered_time else None,
                "acknowledged": a.acknowledged,
            }
            for a in alarms
        ]
    }

# Folders
@app.get("/api/folders")
async def get_folders(
    vcenter_id: Optional[int] = None,
    folder_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get folders."""
    from backend.db_manager import Folder
    session = db_manager.get_local_session()
    
    query = session.query(Folder)
    
    if vcenter_id:
        query = query.filter(Folder.vcenter_id == vcenter_id)
    if folder_type:
        query = query.filter(Folder.folder_type == folder_type)
    
    folders = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(folders),
        "folders": [
            {
                "id": f.id,
                "name": f.name,
                "folder_type": f.folder_type,
                "path": f.path,
            }
            for f in folders
        ]
    }

# vApps
@app.get("/api/vapps")
async def get_vapps(
    vcenter_id: Optional[int] = None,
    power_state: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get vApps."""
    from backend.db_manager import VApp
    session = db_manager.get_local_session()
    
    query = session.query(VApp)
    
    if vcenter_id:
        query = query.filter(VApp.vcenter_id == vcenter_id)
    if power_state:
        query = query.filter(VApp.power_state == power_state)
    
    vapps = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(vapps),
        "vapps": [
            {
                "id": v.id,
                "name": v.name,
                "power_state": v.power_state,
                "vm_count": v.vm_count,
                "cpu_reservation": v.cpu_reservation,
                "memory_reservation": v.memory_reservation,
            }
            for v in vapps
        ]
    }

# Permissions
@app.get("/api/permissions")
async def get_permissions(
    vcenter_id: Optional[int] = None,
    principal: Optional[str] = None,
    is_group: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    username: str = Depends(verify_token)
):
    """Get permissions."""
    from backend.db_manager import Permission
    session = db_manager.get_local_session()
    
    query = session.query(Permission)
    
    if vcenter_id:
        query = query.filter(Permission.vcenter_id == vcenter_id)
    if principal:
        query = query.filter(Permission.principal.like(f"%{principal}%"))
    if is_group is not None:
        query = query.filter(Permission.is_group == is_group)
    
    permissions = query.offset(skip).limit(limit).all()
    session.close()
    
    return {
        "count": len(permissions),
        "permissions": [
            {
                "id": p.id,
                "entity_type": p.entity_type,
                "principal": p.principal,
                "role_name": p.role_name,
                "is_group": p.is_group,
                "propagate": p.propagate,
            }
            for p in permissions
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
