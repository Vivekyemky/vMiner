import logging
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

Base = declarative_base()

class DatabaseManager:
    def __init__(self, local_db_path='inventory.db', sql_connection_string=None):
        self.local_db_path = local_db_path
        self.sql_connection_string = sql_connection_string
        self.local_engine = None
        self.LocalSession = None
        self.sql_engine = None
        self.SqlSession = None

    def init_local_db(self):
        """Initialize the local SQLite database."""
        try:
            self.local_engine = create_engine(f'sqlite:///{self.local_db_path}', echo=False)
            Base.metadata.create_all(self.local_engine)
            self.LocalSession = sessionmaker(bind=self.local_engine)
            logger.info(f"Local database initialized at {self.local_db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize local database: {e}")
            raise

    def connect_sql_source(self):
        """Connect to the source SQL database for vCenter list."""
        if not self.sql_connection_string:
            logger.warning("No SQL connection string provided.")
            return

        try:
            self.sql_engine = create_engine(self.sql_connection_string)
            self.SqlSession = sessionmaker(bind=self.sql_engine)
            # Test connection
            with self.sql_engine.connect() as conn:
                logger.info("Connected to source SQL database successfully.")
        except SQLAlchemyError as e:
            logger.error(f"Failed to connect to source SQL database: {e}")
            raise

    def get_local_session(self):
        if not self.LocalSession:
            self.init_local_db()
        return self.LocalSession()

    def get_sql_session(self):
        if not self.SqlSession:
            self.connect_sql_source()
        return self.SqlSession()

# --- Data Models for Local DB ---

class VCenter(Base):
    __tablename__ = 'vcenters'
    id = Column(Integer, primary_key=True)
    hostname = Column(String, unique=True, nullable=False)
    username = Column(String)
    password = Column(String)  # Encrypted or reference to keyring
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime)
    sync_status = Column(String, default='pending')  # pending, syncing, completed, failed

class VirtualMachine(Base):
    __tablename__ = 'virtual_machines'
    id = Column(Integer, primary_key=True, autoincrement=True)
    moid = Column(String, nullable=False)
    name = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    cluster = Column(String)
    host = Column(String)
    power_state = Column(String)
    cpu_count = Column(Integer)
    memory_mb = Column(Integer)
    ip_address = Column(String)
    os_name = Column(String)
    guest_full_name = Column(String)
    vm_path = Column(String)
    annotation = Column(Text)
    created_date = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow)

class HostSystem(Base):
    __tablename__ = 'hosts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    moid = Column(String, nullable=False)
    name = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    cluster = Column(String)
    connection_state = Column(String)
    power_state = Column(String)
    cpu_mhz = Column(Integer)
    cpu_cores = Column(Integer)
    memory_size = Column(Integer)  # Bytes
    vendor = Column(String)
    model = Column(String)
    vm_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Datastore(Base):
    __tablename__ = 'datastores'
    id = Column(Integer, primary_key=True, autoincrement=True)
    moid = Column(String, nullable=False)
    name = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    type = Column(String)
    capacity = Column(Integer)  # Bytes
    free_space = Column(Integer)  # Bytes
    uncommitted = Column(Integer)  # Bytes
    accessible = Column(Boolean)
    vm_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Cluster(Base):
    __tablename__ = 'clusters'
    id = Column(Integer, primary_key=True, autoincrement=True)
    moid = Column(String, nullable=False)
    name = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    total_cpu = Column(Integer)
    total_memory = Column(Integer)
    num_hosts = Column(Integer, default=0)
    num_vms = Column(Integer, default=0)
    drs_enabled = Column(Boolean)
    ha_enabled = Column(Boolean)
    drs_automation_level = Column(String)  # manual, partiallyAutomated, fullyAutomated
    ha_admission_control = Column(Boolean)
    last_updated = Column(DateTime, default=datetime.utcnow)

# --- Networking Resources ---

class DistributedVirtualSwitch(Base):
    __tablename__ = 'distributed_vswitches'
    id = Column(Integer, primary_key=True, autoincrement=True)
    moid = Column(String, nullable=False)
    name = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    version = Column(String)
    num_ports = Column(Integer)
    num_uplinks = Column(Integer)
    max_ports = Column(Integer)
    network_io_control_enabled = Column(Boolean)
    last_updated = Column(DateTime, default=datetime.utcnow)

class StandardVirtualSwitch(Base):
    __tablename__ = 'standard_vswitches'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    host_moid = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    num_ports = Column(Integer)
    mtu = Column(Integer)
    num_uplinks = Column(Integer)
    last_updated = Column(DateTime, default=datetime.utcnow)

class PortGroup(Base):
    __tablename__ = 'port_groups'
    id = Column(Integer, primary_key=True, autoincrement=True)
    moid = Column(String, nullable=False)
    name = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    vswitch_name = Column(String)
    vlan_id = Column(Integer)
    num_ports = Column(Integer)
    port_binding = Column(String)  # static, dynamic, ephemeral
    vm_count = Column(Integer, default=0)
    is_distributed = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=datetime.utcnow)

class NetworkAdapter(Base):
    __tablename__ = 'network_adapters'
    id = Column(Integer, primary_key=True, autoincrement=True)
    vm_moid = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    adapter_type = Column(String)  # VMXNET3, E1000, etc.
    mac_address = Column(String)
    network_name = Column(String)
    connected = Column(Boolean)
    start_connected = Column(Boolean)
    last_updated = Column(DateTime, default=datetime.utcnow)

# --- Storage Resources ---

class StorageAdapter(Base):
    __tablename__ = 'storage_adapters'
    id = Column(Integer, primary_key=True, autoincrement=True)
    host_moid = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    device = Column(String)
    adapter_type = Column(String)  # FibreChannel, iSCSI, Block
    model = Column(String)
    driver = Column(String)
    pci = Column(String)
    status = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)

class ScsiLun(Base):
    __tablename__ = 'scsi_luns'
    id = Column(Integer, primary_key=True, autoincrement=True)
    host_moid = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    canonical_name = Column(String)
    display_name = Column(String)
    lun_type = Column(String)
    vendor = Column(String)
    model = Column(String)
    capacity_mb = Column(Integer)
    multipath_policy = Column(String)
    path_count = Column(Integer)
    last_updated = Column(DateTime, default=datetime.utcnow)

# --- Resource Management ---

class ResourcePool(Base):
    __tablename__ = 'resource_pools'
    id = Column(Integer, primary_key=True, autoincrement=True)
    moid = Column(String, nullable=False)
    name = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    cluster_moid = Column(String)
    parent_moid = Column(String)
    cpu_reservation = Column(Integer)
    cpu_limit = Column(Integer)
    cpu_shares = Column(Integer)
    memory_reservation = Column(Integer)
    memory_limit = Column(Integer)
    memory_shares = Column(Integer)
    expandable_reservation = Column(Boolean)
    vm_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class VApp(Base):
    __tablename__ = 'vapps'
    id = Column(Integer, primary_key=True, autoincrement=True)
    moid = Column(String, nullable=False)
    name = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    power_state = Column(String)
    vm_count = Column(Integer, default=0)
    cpu_reservation = Column(Integer)
    memory_reservation = Column(Integer)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Folder(Base):
    __tablename__ = 'folders'
    id = Column(Integer, primary_key=True, autoincrement=True)
    moid = Column(String, nullable=False)
    name = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    folder_type = Column(String)  # vm, host, datastore, network
    parent_moid = Column(String)
    path = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)

# --- Snapshots ---

class Snapshot(Base):
    __tablename__ = 'snapshots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    vm_moid = Column(String, nullable=False)
    snapshot_moid = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    vm_name = Column(String)
    snapshot_name = Column(String)
    description = Column(Text)
    created_date = Column(DateTime)
    size_mb = Column(Integer)
    quiesced = Column(Boolean)
    parent_snapshot_moid = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)

# --- Templates & Content Libraries ---

class VMTemplate(Base):
    __tablename__ = 'vm_templates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    moid = Column(String, nullable=False)
    name = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    guest_os = Column(String)
    cpu_count = Column(Integer)
    memory_mb = Column(Integer)
    num_disks = Column(Integer)
    folder_moid = Column(String)
    annotation = Column(Text)
    last_updated = Column(DateTime, default=datetime.utcnow)

class ContentLibrary(Base):
    __tablename__ = 'content_libraries'
    id = Column(Integer, primary_key=True, autoincrement=True)
    library_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    library_type = Column(String)  # LOCAL, SUBSCRIBED
    storage_backing = Column(String)
    item_count = Column(Integer, default=0)
    published = Column(Boolean)
    last_updated = Column(DateTime, default=datetime.utcnow)

# --- DRS & HA Rules ---

class DRSRule(Base):
    __tablename__ = 'drs_rules'
    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_moid = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    rule_name = Column(String)
    rule_type = Column(String)  # affinity, anti-affinity, vm-host
    enabled = Column(Boolean)
    mandatory = Column(Boolean)
    vm_moids = Column(Text)  # JSON array
    last_updated = Column(DateTime, default=datetime.utcnow)

# --- Performance Metrics ---

class VMPerformance(Base):
    __tablename__ = 'vm_performance'
    id = Column(Integer, primary_key=True, autoincrement=True)
    vm_moid = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    cpu_usage_mhz = Column(Integer)
    cpu_usage_percent = Column(Float)
    memory_usage_mb = Column(Integer)
    memory_active_mb = Column(Integer)
    disk_read_iops = Column(Integer)
    disk_write_iops = Column(Integer)
    disk_read_latency_ms = Column(Float)
    disk_write_latency_ms = Column(Float)
    network_rx_mbps = Column(Float)
    network_tx_mbps = Column(Float)

class HostPerformance(Base):
    __tablename__ = 'host_performance'
    id = Column(Integer, primary_key=True, autoincrement=True)
    host_moid = Column(String, nullable=False)
    vcenter_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    cpu_usage_mhz = Column(Integer)
    cpu_usage_percent = Column(Float)
    memory_usage_mb = Column(Integer)
    memory_active_mb = Column(Integer)
    memory_ballooned_mb = Column(Integer)
    memory_swapped_mb = Column(Integer)
    disk_latency_ms = Column(Float)
    network_throughput_mbps = Column(Float)

# --- Events & Alarms ---

class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True, autoincrement=True)
    vcenter_id = Column(Integer, nullable=False)
    event_type = Column(String)
    severity = Column(String)  # info, warning, error
    timestamp = Column(DateTime)
    user_name = Column(String)
    entity_moid = Column(String)
    entity_name = Column(String)
    message = Column(Text)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Alarm(Base):
    __tablename__ = 'alarms'
    id = Column(Integer, primary_key=True, autoincrement=True)
    vcenter_id = Column(Integer, nullable=False)
    alarm_name = Column(String)
    entity_moid = Column(String)
    entity_name = Column(String)
    status = Column(String)  # red, yellow, green, gray
    triggered_time = Column(DateTime)
    acknowledged = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=datetime.utcnow)

# --- Users & Permissions ---

class Permission(Base):
    __tablename__ = 'permissions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    vcenter_id = Column(Integer, nullable=False)
    entity_moid = Column(String)
    entity_type = Column(String)
    principal = Column(String)  # user or group name
    role_name = Column(String)
    is_group = Column(Boolean)
    propagate = Column(Boolean)
    last_updated = Column(DateTime, default=datetime.utcnow)

# --- Custom Attributes & Tags ---

class CustomAttribute(Base):
    __tablename__ = 'custom_attributes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    vcenter_id = Column(Integer, nullable=False)
    entity_moid = Column(String)
    entity_type = Column(String)
    attribute_name = Column(String)
    attribute_value = Column(Text)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Tag(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True, autoincrement=True)
    vcenter_id = Column(Integer, nullable=False)
    tag_id = Column(String)
    tag_name = Column(String)
    category_name = Column(String)
    description = Column(Text)
    entity_moid = Column(String)
    entity_type = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)

# --- Tasks ---

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    vcenter_id = Column(Integer, nullable=False)
    task_moid = Column(String)
    task_name = Column(String)
    state = Column(String)  # queued, running, success, error
    entity_moid = Column(String)
    entity_name = Column(String)
    initiated_by = Column(String)
    start_time = Column(DateTime)
    complete_time = Column(DateTime)
    progress = Column(Integer)
    error_message = Column(Text)
    last_updated = Column(DateTime, default=datetime.utcnow)
