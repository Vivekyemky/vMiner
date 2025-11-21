# vMiner - Hyper-Scale Architecture (1000+ vCenters)

## Your Scale Requirements

### Estimated Inventory
- **vCenters**: 1,000+
- **VMs**: 500,000 - 1,000,000+
- **Hosts**: 50,000 - 100,000+
- **Datastores**: 10,000 - 20,000+
- **Concurrent Users**: 500 - 2,000+

## Required Architecture Changes

### ⚠️ Critical: SQLite is NOT suitable for your scale

You **must** use a distributed architecture. Here's the recommended setup:

## Recommended Architecture

```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    │   (HAProxy/     │
                    │    AWS ALB)     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │  API #1  │   │  API #2  │   │  API #3  │  (5-10 instances)
        │ (FastAPI)│   │ (FastAPI)│   │ (FastAPI)│
        └─────┬────┘   └─────┬────┘   └─────┬────┘
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                    ┌─────────────────┐
                    │  Redis Cluster  │  (Query Cache)
                    │   (16-32 GB)    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │PostgreSQL│   │PostgreSQL│   │PostgreSQL│
        │ Primary  │──▶│ Replica 1│   │ Replica 2│
        │(Write)   │   │ (Read)   │   │ (Read)   │
        └──────────┘   └──────────┘   └──────────┘
              │
              ▼
        ┌──────────┐
        │ Message  │  (RabbitMQ/Kafka for sync jobs)
        │  Queue   │
        └──────────┘
              │
              ▼
        ┌──────────┐
        │  Sync    │  (Dedicated sync workers)
        │ Workers  │  (10-20 instances)
        └──────────┘
```

## Infrastructure Specifications

### 1. API Servers (5-10 instances)
```
CPU:     8 cores each
RAM:     16 GB each
Disk:    100 GB SSD
OS:      Linux (Ubuntu/RHEL)
Purpose: Handle API requests, query processing
```

### 2. PostgreSQL Cluster

#### Primary (Write)
```
CPU:     32 cores
RAM:     128 GB
Disk:    2 TB NVMe SSD (RAID 10)
IOPS:    50,000+
Purpose: Handle all writes (sync operations)
```

#### Read Replicas (3-5 instances)
```
CPU:     16 cores each
RAM:     64 GB each
Disk:    2 TB SSD each
Purpose: Handle read queries (API queries)
```

### 3. Redis Cache Cluster
```
CPU:     8 cores
RAM:     32 GB (cache size)
Purpose: Cache frequent queries, reduce DB load
TTL:     5-10 minutes
```

### 4. Sync Workers (10-20 instances)
```
CPU:     8 cores each
RAM:     16 GB each
Purpose: Dedicated vCenter sync operations
Workers: 50-100 concurrent vCenter connections
```

### 5. Message Queue (RabbitMQ/Kafka)
```
CPU:     8 cores
RAM:     16 GB
Purpose: Distribute sync jobs to workers
```

## Performance Estimates

### Sync Operations
```
Total vCenters:     1,000
Concurrent Workers: 100
Avg VMs/vCenter:    500
Total VMs:          500,000

Initial Sync Time:  2-3 hours
Incremental Sync:   30-45 minutes
Sync Frequency:     Every 1-2 hours
```

### Query Performance
```
Simple Query:       <50ms
Complex Query:      <200ms
Large Result Set:   <500ms
Concurrent Users:   2,000+
Throughput:         10,000+ queries/minute
```

### Storage Requirements
```
Database Size:      500 GB - 1 TB
Backup Size:        500 GB - 1 TB
Logs:              100 GB/month
Total:             1.5 - 2.5 TB
```

## Implementation Changes Required

### 1. Database Configuration

Create `config/database.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# Primary database (writes)
PRIMARY_DB = "postgresql://user:pass@primary-db:5432/vminer"

# Read replicas (queries)
READ_REPLICAS = [
    "postgresql://user:pass@replica1-db:5432/vminer",
    "postgresql://user:pass@replica2-db:5432/vminer",
    "postgresql://user:pass@replica3-db:5432/vminer",
]

# Connection pool settings for high concurrency
engine_primary = create_engine(
    PRIMARY_DB,
    poolclass=QueuePool,
    pool_size=50,
    max_overflow=100,
    pool_pre_ping=True
)

# Round-robin read replicas
import random
def get_read_engine():
    replica = random.choice(READ_REPLICAS)
    return create_engine(
        replica,
        poolclass=QueuePool,
        pool_size=30,
        max_overflow=50
    )
```

### 2. Redis Caching Layer

Create `utils/cache.py`:
```python
import redis
import json
from functools import wraps

redis_client = redis.Redis(
    host='redis-cluster',
    port=6379,
    db=0,
    decode_responses=True
)

def cache_query(ttl=300):  # 5 minutes default
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function and args
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Execute query
            result = await func(*args, **kwargs)
            
            # Store in cache
            redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result, default=str)
            )
            
            return result
        return wrapper
    return decorator
```

### 3. Distributed Sync with Message Queue

Create `backend/distributed_sync.py`:
```python
import pika
import json
from concurrent.futures import ThreadPoolExecutor

class DistributedSyncEngine:
    def __init__(self, rabbitmq_host='localhost'):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=rabbitmq_host)
        )
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='vcenter_sync', durable=True)
    
    def queue_vcenter_sync(self, vcenter_id):
        """Queue a vCenter for sync"""
        message = json.dumps({'vcenter_id': vcenter_id})
        self.channel.basic_publish(
            exchange='',
            routing_key='vcenter_sync',
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent
            )
        )
    
    def queue_all_vcenters(self):
        """Queue all vCenters for sync"""
        session = db_manager.get_local_session()
        vcenters = session.query(VCenter).filter(
            VCenter.is_active == True
        ).all()
        
        for vc in vcenters:
            self.queue_vcenter_sync(vc.id)
        
        session.close()
        print(f"Queued {len(vcenters)} vCenters for sync")
```

### 4. Partitioning Strategy

For 1000+ vCenters, partition data by vCenter:

```sql
-- PostgreSQL table partitioning
CREATE TABLE virtual_machines (
    id SERIAL,
    vcenter_id INTEGER NOT NULL,
    name VARCHAR(255),
    -- other fields
) PARTITION BY HASH (vcenter_id);

-- Create 100 partitions (10 vCenters per partition)
CREATE TABLE vms_p0 PARTITION OF virtual_machines
    FOR VALUES WITH (MODULUS 100, REMAINDER 0);
    
CREATE TABLE vms_p1 PARTITION OF virtual_machines
    FOR VALUES WITH (MODULUS 100, REMAINDER 1);
    
-- ... create remaining partitions
```

### 5. Optimized Indexes

```sql
-- Critical indexes for 1M+ VMs
CREATE INDEX CONCURRENTLY idx_vm_vcenter_power 
    ON virtual_machines(vcenter_id, power_state);

CREATE INDEX CONCURRENTLY idx_vm_cluster 
    ON virtual_machines(cluster) 
    WHERE cluster IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_vm_name_trgm 
    ON virtual_machines USING gin(name gin_trgm_ops);

CREATE INDEX CONCURRENTLY idx_host_vcenter_cluster 
    ON hosts(vcenter_id, cluster);

-- Partial indexes for common queries
CREATE INDEX idx_vm_powered_on 
    ON virtual_machines(vcenter_id) 
    WHERE power_state = 'poweredOn';
```

## Deployment Architecture

### Cloud Deployment (AWS Example)

```
Region: us-east-1

VPC:
├── Public Subnet (Load Balancer)
│   └── Application Load Balancer
│
├── Private Subnet 1 (API Tier)
│   ├── API Server 1 (EC2 c5.2xlarge)
│   ├── API Server 2 (EC2 c5.2xlarge)
│   ├── API Server 3 (EC2 c5.2xlarge)
│   ├── API Server 4 (EC2 c5.2xlarge)
│   └── API Server 5 (EC2 c5.2xlarge)
│
├── Private Subnet 2 (Database Tier)
│   ├── RDS PostgreSQL (db.r5.4xlarge)
│   │   ├── Primary (Multi-AZ)
│   │   └── Read Replicas (3x)
│   └── ElastiCache Redis (cache.r5.xlarge)
│
└── Private Subnet 3 (Worker Tier)
    ├── Sync Worker 1 (EC2 c5.2xlarge)
    ├── Sync Worker 2 (EC2 c5.2xlarge)
    ├── ... (10-20 workers)
    └── RabbitMQ (EC2 t3.large)
```

### Cost Estimate (AWS)

```
Component               Instance Type    Count   Monthly Cost
-----------------------------------------------------------------
Load Balancer          ALB              1       $25
API Servers            c5.2xlarge       5       $750
RDS Primary            db.r5.4xlarge    1       $1,200
RDS Replicas           db.r5.2xlarge    3       $1,800
ElastiCache Redis      cache.r5.xlarge  1       $250
Sync Workers           c5.2xlarge       10      $1,500
RabbitMQ               t3.large         1       $75
Storage (2TB)          EBS SSD          -       $200
Data Transfer          -                -       $200
-----------------------------------------------------------------
TOTAL:                                          ~$6,000/month

With Reserved Instances (1-year): ~$4,000/month
```

## Migration Steps for Your Scale

### Phase 1: Database Migration (Week 1-2)
1. Set up PostgreSQL cluster
2. Migrate schema from SQLite
3. Add partitioning
4. Create indexes
5. Test performance

### Phase 2: Caching Layer (Week 2-3)
1. Deploy Redis cluster
2. Implement cache layer
3. Update query engine
4. Test cache hit rates

### Phase 3: Distributed Sync (Week 3-4)
1. Deploy RabbitMQ
2. Implement distributed sync
3. Deploy sync workers
4. Test sync performance

### Phase 4: API Scaling (Week 4-5)
1. Deploy multiple API instances
2. Configure load balancer
3. Test concurrent load
4. Optimize performance

### Phase 5: Production Rollout (Week 5-6)
1. Gradual rollout (10% → 50% → 100%)
2. Monitor performance
3. Tune configuration
4. Full production

## Monitoring & Observability

### Required Monitoring

```
Metrics to Track:
├── API Performance
│   ├── Request rate (requests/sec)
│   ├── Response time (p50, p95, p99)
│   ├── Error rate (%)
│   └── Concurrent connections
│
├── Database Performance
│   ├── Query time (ms)
│   ├── Connection pool usage
│   ├── Replication lag (ms)
│   └── Disk I/O (IOPS)
│
├── Sync Performance
│   ├── vCenters synced/hour
│   ├── Sync success rate (%)
│   ├── Average sync time (min)
│   └── Queue depth
│
└── System Resources
    ├── CPU usage (%)
    ├── Memory usage (%)
    ├── Disk usage (%)
    └── Network throughput (Mbps)
```

### Recommended Tools
- **Prometheus** + **Grafana**: Metrics and dashboards
- **ELK Stack**: Centralized logging
- **Datadog/New Relic**: APM and monitoring
- **PagerDuty**: Alerting

## Performance Tuning

### PostgreSQL Configuration

```ini
# postgresql.conf for high-scale deployment

# Memory
shared_buffers = 32GB
effective_cache_size = 96GB
work_mem = 64MB
maintenance_work_mem = 2GB

# Connections
max_connections = 500

# Checkpoints
checkpoint_completion_target = 0.9
wal_buffers = 16MB
max_wal_size = 4GB

# Query Planner
random_page_cost = 1.1  # For SSD
effective_io_concurrency = 200

# Parallel Query
max_parallel_workers_per_gather = 4
max_parallel_workers = 16
```

### API Server Configuration

```python
# main.py updates for scale

# Increase worker processes
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=16,  # CPU cores
        limit_concurrency=1000,
        backlog=2048
    )
```

## Summary

For **1000+ vCenters**, you need:

### Must Have
✅ PostgreSQL cluster (not SQLite)
✅ Redis caching layer
✅ Distributed sync workers
✅ Load balancer
✅ Message queue (RabbitMQ/Kafka)

### Recommended
✅ Table partitioning
✅ Read replicas (3-5)
✅ Monitoring stack
✅ Auto-scaling
✅ Multi-region deployment

### Expected Performance
- **Initial Sync**: 2-3 hours for all 1000 vCenters
- **Incremental Sync**: 30-45 minutes
- **Query Response**: <200ms for 95% of queries
- **Concurrent Users**: 2,000+
- **Uptime**: 99.9%+

The current codebase provides a solid foundation, but you'll need to implement the distributed architecture components for your scale! 🚀
