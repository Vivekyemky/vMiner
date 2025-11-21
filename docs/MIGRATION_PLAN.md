# Migration Plan: Current → Hyper-Scale (1000+ vCenters)

## Overview

This document provides a detailed, step-by-step migration plan from the current single-server SQLite setup to a distributed hyper-scale architecture supporting 1000+ vCenters.

**Timeline**: 8-12 weeks
**Risk Level**: Medium
**Downtime Required**: Minimal (< 4 hours for final cutover)

## Pre-Migration Checklist

- [ ] Infrastructure provisioning approved
- [ ] Budget approved (~$6,000/month cloud costs)
- [ ] Team trained on new architecture
- [ ] Backup and rollback plan documented
- [ ] Monitoring and alerting configured
- [ ] Load testing environment set up

## Phase 1: Infrastructure Setup (Week 1-2)

### Week 1: Core Infrastructure

#### Day 1-2: PostgreSQL Cluster Setup

**Tasks:**
1. Provision PostgreSQL primary instance
   - Instance: AWS RDS db.r5.4xlarge or equivalent
   - Storage: 2 TB SSD with auto-scaling
   - Multi-AZ deployment for HA
   
2. Configure PostgreSQL for high performance
   ```sql
   -- Apply these settings
   shared_buffers = 32GB
   effective_cache_size = 96GB
   work_mem = 64MB
   max_connections = 500
   ```

3. Create database and user
   ```sql
   CREATE DATABASE vminer;
   CREATE USER vminer_app WITH PASSWORD 'secure-password';
   GRANT ALL PRIVILEGES ON DATABASE vminer TO vminer_app;
   ```

**Verification:**
```bash
# Test connection
psql -h primary-db-host -U vminer_app -d vminer -c "SELECT version();"
```

#### Day 3-4: Read Replicas Setup

**Tasks:**
1. Create 3 read replicas from primary
2. Configure replication lag monitoring
3. Test failover scenarios

**Verification:**
```sql
-- Check replication lag (should be < 100ms)
SELECT 
    client_addr,
    state,
    sync_state,
    replay_lag
FROM pg_stat_replication;
```

#### Day 5: Redis Cache Setup

**Tasks:**
1. Provision Redis cluster
   - Instance: AWS ElastiCache cache.r5.xlarge
   - Memory: 32 GB
   - Cluster mode enabled

2. Configure Redis
   ```conf
   maxmemory 30gb
   maxmemory-policy allkeys-lru
   timeout 300
   ```

**Verification:**
```bash
redis-cli -h redis-host ping
# Should return: PONG
```

### Week 2: Application Infrastructure

#### Day 1-2: Message Queue Setup

**Tasks:**
1. Deploy RabbitMQ cluster
   - 3 nodes for HA
   - Disk-backed queues
   
2. Create queues and exchanges
   ```bash
   # Create sync queue
   rabbitmqadmin declare queue name=vcenter_sync durable=true
   
   # Create dead letter queue
   rabbitmqadmin declare queue name=vcenter_sync_dlq durable=true
   ```

**Verification:**
```bash
rabbitmqctl list_queues
```

#### Day 3-4: Load Balancer Setup

**Tasks:**
1. Configure Application Load Balancer
   - Health check: GET /health
   - Sticky sessions: Enabled
   - SSL/TLS termination

2. Configure target groups
   - API servers (port 8000)
   - Health check interval: 30s

#### Day 5: Monitoring Stack

**Tasks:**
1. Deploy Prometheus
2. Deploy Grafana
3. Configure dashboards
4. Set up alerts

**Deliverables:**
- [ ] PostgreSQL cluster running
- [ ] Redis cache operational
- [ ] RabbitMQ cluster ready
- [ ] Load balancer configured
- [ ] Monitoring active

## Phase 2: Database Migration (Week 3-4)

### Week 3: Schema Migration

#### Day 1-2: Export Current Data

**Tasks:**
1. Stop current sync operations
2. Create full backup
   ```bash
   # Backup SQLite
   sqlite3 inventory.db .dump > backup_$(date +%Y%m%d).sql
   
   # Backup to S3
   aws s3 cp backup_*.sql s3://vminer-backups/
   ```

3. Document current data statistics
   ```sql
   SELECT 
       'VMs' as entity,
       COUNT(*) as count,
       pg_size_pretty(pg_total_relation_size('virtual_machines')) as size
   FROM virtual_machines
   UNION ALL
   SELECT 'Hosts', COUNT(*), pg_size_pretty(pg_total_relation_size('hosts'))
   FROM hosts;
   ```

#### Day 3-4: Create PostgreSQL Schema

**Tasks:**
1. Update `backend/db_manager.py` for PostgreSQL
2. Create partitioned tables
   ```sql
   -- Create partitioned VM table
   CREATE TABLE virtual_machines (
       id SERIAL,
       vcenter_id INTEGER NOT NULL,
       moid VARCHAR(50) NOT NULL,
       name VARCHAR(255) NOT NULL,
       cluster VARCHAR(255),
       host VARCHAR(255),
       power_state VARCHAR(50),
       cpu_count INTEGER,
       memory_mb INTEGER,
       ip_address VARCHAR(50),
       os_name VARCHAR(255),
       guest_full_name VARCHAR(255),
       vm_path TEXT,
       annotation TEXT,
       created_date TIMESTAMP,
       last_updated TIMESTAMP DEFAULT NOW(),
       PRIMARY KEY (id, vcenter_id)
   ) PARTITION BY HASH (vcenter_id);
   
   -- Create 100 partitions (10 vCenters per partition)
   DO $$
   BEGIN
       FOR i IN 0..99 LOOP
           EXECUTE format('
               CREATE TABLE virtual_machines_p%s PARTITION OF virtual_machines
               FOR VALUES WITH (MODULUS 100, REMAINDER %s)',
               i, i
           );
       END LOOP;
   END $$;
   ```

3. Create indexes
   ```sql
   -- Critical indexes
   CREATE INDEX CONCURRENTLY idx_vm_vcenter_power 
       ON virtual_machines(vcenter_id, power_state);
   
   CREATE INDEX CONCURRENTLY idx_vm_cluster 
       ON virtual_machines(cluster) 
       WHERE cluster IS NOT NULL;
   
   CREATE INDEX CONCURRENTLY idx_vm_name 
       ON virtual_machines(name);
   
   -- Repeat for hosts, datastores, clusters
   ```

#### Day 5: Data Migration

**Tasks:**
1. Convert SQLite dump to PostgreSQL format
   ```bash
   # Use pgloader for migration
   pgloader sqlite://inventory.db postgresql://user:pass@host/vminer
   ```

2. Verify data integrity
   ```sql
   -- Compare counts
   SELECT 
       (SELECT COUNT(*) FROM virtual_machines) as vms,
       (SELECT COUNT(*) FROM hosts) as hosts,
       (SELECT COUNT(*) FROM datastores) as datastores;
   ```

### Week 4: Application Updates

#### Day 1-3: Update Database Layer

**File: `backend/db_manager_postgres.py`** (new file)
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
import random

class PostgreSQLManager:
    def __init__(self):
        # Primary for writes
        self.primary_engine = create_engine(
            os.getenv("PRIMARY_DATABASE_URL"),
            poolclass=QueuePool,
            pool_size=50,
            max_overflow=100,
            pool_pre_ping=True,
            echo=False
        )
        
        # Read replicas
        replica_urls = os.getenv("READ_REPLICA_URLS", "").split(",")
        self.replica_engines = [
            create_engine(
                url,
                poolclass=QueuePool,
                pool_size=30,
                max_overflow=50,
                pool_pre_ping=True
            )
            for url in replica_urls if url
        ]
    
    def get_write_session(self):
        """Get session for write operations (sync)"""
        Session = sessionmaker(bind=self.primary_engine)
        return Session()
    
    def get_read_session(self):
        """Get session for read operations (queries)"""
        # Round-robin read replicas
        engine = random.choice(self.replica_engines) if self.replica_engines else self.primary_engine
        Session = sessionmaker(bind=engine)
        return Session()
```

#### Day 4-5: Update Query Engine

**File: `backend/query_engine_cached.py`** (new file)
```python
import redis
import json
from functools import wraps
import hashlib

class CachedQueryEngine(QueryEngine):
    def __init__(self, db_manager):
        super().__init__(db_manager)
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=0,
            decode_responses=True,
            socket_connect_timeout=5
        )
    
    def parse_and_execute(self, query: str) -> Dict[str, Any]:
        # Generate cache key
        cache_key = f"query:{hashlib.md5(query.encode()).hexdigest()}"
        
        # Try cache first
        try:
            cached = self.redis_client.get(cache_key)
            if cached:
                logger.info(f"Cache HIT for query: {query}")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache error: {e}")
        
        # Execute query
        result = super().parse_and_execute(query)
        
        # Store in cache (5 minute TTL)
        try:
            self.redis_client.setex(
                cache_key,
                300,
                json.dumps(result, default=str)
            )
        except Exception as e:
            logger.warning(f"Cache store error: {e}")
        
        return result
```

**Deliverables:**
- [ ] PostgreSQL schema created with partitions
- [ ] Data migrated and verified
- [ ] Application updated for PostgreSQL
- [ ] Redis caching implemented

## Phase 3: Distributed Sync Implementation (Week 5-6)

### Week 5: Message Queue Integration

#### Day 1-2: Implement Distributed Sync

**File: `backend/distributed_sync.py`** (create new)
```python
import pika
import json
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

class DistributedSyncEngine:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
        self.connection = None
        self.channel = None
    
    def connect(self):
        """Connect to RabbitMQ"""
        credentials = pika.PlainCredentials(
            os.getenv("RABBITMQ_USER", "guest"),
            os.getenv("RABBITMQ_PASSWORD", "guest")
        )
        parameters = pika.ConnectionParameters(
            host=self.rabbitmq_host,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        
        # Declare queue
        self.channel.queue_declare(
            queue='vcenter_sync',
            durable=True,
            arguments={
                'x-max-priority': 10,
                'x-message-ttl': 3600000  # 1 hour
            }
        )
    
    def queue_vcenter_sync(self, vcenter_id, priority=5):
        """Queue a single vCenter for sync"""
        if not self.channel:
            self.connect()
        
        message = json.dumps({
            'vcenter_id': vcenter_id,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        self.channel.basic_publish(
            exchange='',
            routing_key='vcenter_sync',
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent
                priority=priority
            )
        )
        logger.info(f"Queued vCenter {vcenter_id} for sync")
    
    def queue_all_vcenters(self):
        """Queue all active vCenters"""
        session = self.db_manager.get_read_session()
        vcenters = session.query(VCenter).filter(
            VCenter.is_active == True
        ).all()
        
        for vc in vcenters:
            self.queue_vcenter_sync(vc.id)
        
        session.close()
        logger.info(f"Queued {len(vcenters)} vCenters for sync")
        return len(vcenters)
```

#### Day 3-5: Implement Sync Worker

**File: `workers/sync_worker.py`** (create new)
```python
import pika
import json
from backend.vcenter_client import VCenterClient
from backend.db_manager_postgres import PostgreSQLManager

class SyncWorker:
    def __init__(self, worker_id):
        self.worker_id = worker_id
        self.db_manager = PostgreSQLManager()
        self.rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
    
    def start(self):
        """Start consuming sync jobs"""
        credentials = pika.PlainCredentials(
            os.getenv("RABBITMQ_USER", "guest"),
            os.getenv("RABBITMQ_PASSWORD", "guest")
        )
        parameters = pika.ConnectionParameters(
            host=self.rabbitmq_host,
            credentials=credentials
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Set QoS - process 10 messages at a time
        channel.basic_qos(prefetch_count=10)
        
        # Start consuming
        channel.basic_consume(
            queue='vcenter_sync',
            on_message_callback=self.process_sync_job,
            auto_ack=False
        )
        
        logger.info(f"Worker {self.worker_id} started, waiting for jobs...")
        channel.start_consuming()
    
    def process_sync_job(self, ch, method, properties, body):
        """Process a single sync job"""
        try:
            message = json.loads(body)
            vcenter_id = message['vcenter_id']
            
            logger.info(f"Worker {self.worker_id} processing vCenter {vcenter_id}")
            
            # Get vCenter details
            session = self.db_manager.get_read_session()
            vcenter = session.query(VCenter).filter(
                VCenter.id == vcenter_id
            ).first()
            session.close()
            
            if not vcenter:
                logger.error(f"vCenter {vcenter_id} not found")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return
            
            # Perform sync
            result = self._sync_vcenter(vcenter)
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Worker {self.worker_id} completed vCenter {vcenter_id}: {result}")
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id} error: {e}")
            # Requeue on error
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def _sync_vcenter(self, vcenter):
        """Sync a single vCenter (same logic as before)"""
        # ... existing sync logic ...
        pass

if __name__ == "__main__":
    import sys
    worker_id = sys.argv[1] if len(sys.argv) > 1 else "1"
    worker = SyncWorker(worker_id)
    worker.start()
```

### Week 6: API Server Scaling

#### Day 1-2: Update Main Application

**File: `main.py`** (update)
```python
# Add at top
from backend.db_manager_postgres import PostgreSQLManager
from backend.query_engine_cached import CachedQueryEngine
from backend.distributed_sync import DistributedSyncEngine

# Replace db_manager initialization
db_manager = PostgreSQLManager()
query_engine = CachedQueryEngine(db_manager)
sync_engine = DistributedSyncEngine(db_manager)

# Add health check endpoint
@app.get("/health")
async def health_check():
    """Health check for load balancer"""
    try:
        # Check database
        session = db_manager.get_read_session()
        session.execute("SELECT 1")
        session.close()
        
        # Check Redis
        query_engine.redis_client.ping()
        
        return {"status": "healthy"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

# Update sync endpoint
@app.post("/api/vcenters/sync")
async def sync_vcenters(
    request: SyncRequest,
    username: str = Depends(verify_token)
):
    """Trigger vCenter synchronization via queue"""
    if request.vcenter_ids:
        for vcenter_id in request.vcenter_ids:
            sync_engine.queue_vcenter_sync(vcenter_id)
        return {"message": f"Queued {len(request.vcenter_ids)} vCenters for sync"}
    else:
        count = sync_engine.queue_all_vcenters()
        return {"message": f"Queued {count} vCenters for sync"}
```

#### Day 3-5: Deploy Multiple API Instances

**Tasks:**
1. Create API server deployment script
2. Configure auto-scaling
3. Test load distribution

**Deliverables:**
- [ ] Distributed sync implemented
- [ ] Sync workers deployed
- [ ] Multiple API instances running
- [ ] Load balancer distributing traffic

## Phase 4: Testing & Optimization (Week 7-8)

### Week 7: Load Testing

#### Day 1-3: Performance Testing

**Create load test script:**
```python
# tests/load_test.py
from locust import HttpUser, task, between
import random

class VMinerUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login
        response = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def query_vms(self):
        queries = [
            "get all powered on VMs",
            "show me hosts with no vms",
            "get all empty datastores",
            "count powered off vms"
        ]
        self.client.post(
            "/api/query/chat",
            headers=self.headers,
            json={"query": random.choice(queries)}
        )
    
    @task(1)
    def get_stats(self):
        self.client.get("/api/stats", headers=self.headers)
```

**Run load test:**
```bash
# Test with 1000 concurrent users
locust -f tests/load_test.py --host=http://load-balancer-url --users 1000 --spawn-rate 50
```

**Success Criteria:**
- [ ] 95th percentile response time < 200ms
- [ ] Error rate < 0.1%
- [ ] Sustained 10,000+ requests/minute
- [ ] No memory leaks over 24 hours

#### Day 4-5: Sync Performance Testing

**Tasks:**
1. Queue 1000 vCenters for sync
2. Monitor completion time
3. Verify data accuracy

**Success Criteria:**
- [ ] All 1000 vCenters sync in < 3 hours
- [ ] No sync failures
- [ ] Data integrity 100%

### Week 8: Optimization

#### Day 1-2: Database Tuning

**Tasks:**
1. Analyze slow queries
   ```sql
   -- Enable pg_stat_statements
   CREATE EXTENSION pg_stat_statements;
   
   -- Find slow queries
   SELECT 
       query,
       calls,
       mean_exec_time,
       max_exec_time
   FROM pg_stat_statements
   ORDER BY mean_exec_time DESC
   LIMIT 20;
   ```

2. Add missing indexes
3. Optimize query plans

#### Day 3-4: Cache Optimization

**Tasks:**
1. Analyze cache hit rates
   ```python
   # Add to query engine
   def get_cache_stats(self):
       info = self.redis_client.info('stats')
       hit_rate = info['keyspace_hits'] / (info['keyspace_hits'] + info['keyspace_misses'])
       return {
           'hit_rate': hit_rate,
           'hits': info['keyspace_hits'],
           'misses': info['keyspace_misses']
       }
   ```

2. Adjust TTL values
3. Implement cache warming

**Target:** >80% cache hit rate

#### Day 5: Final Verification

**Checklist:**
- [ ] All 1000 vCenters syncing successfully
- [ ] Query performance meets SLA
- [ ] Monitoring and alerts working
- [ ] Backup and recovery tested
- [ ] Documentation updated

## Phase 5: Production Cutover (Week 9-10)

### Week 9: Pre-Production

#### Day 1-3: Parallel Run

**Tasks:**
1. Run old and new systems in parallel
2. Compare results
3. Fix any discrepancies

#### Day 4-5: User Acceptance Testing

**Tasks:**
1. Train users on new system
2. Conduct UAT
3. Gather feedback

### Week 10: Go-Live

#### Day 1: Final Preparation

**Tasks:**
- [ ] Final backup of old system
- [ ] Verify all services healthy
- [ ] Communication to users
- [ ] Rollback plan ready

#### Day 2: Cutover (4-hour window)

**Timeline:**
```
00:00 - Announce maintenance window
00:15 - Stop old system sync
00:30 - Final data sync to new system
01:00 - Verify data integrity
01:30 - Switch DNS/Load balancer to new system
02:00 - Monitor for issues
03:00 - Verify all features working
04:00 - Maintenance window complete
```

#### Day 3-5: Post-Go-Live Support

**Tasks:**
- Monitor system closely
- Address any issues immediately
- Optimize based on real usage
- Collect user feedback

## Rollback Plan

If critical issues occur:

1. **Immediate (< 1 hour):**
   - Switch load balancer back to old system
   - Announce rollback to users

2. **Data Sync (1-2 hours):**
   - Sync any new data from new system to old
   - Verify data integrity

3. **Root Cause Analysis:**
   - Identify issue
   - Fix in staging
   - Plan retry

## Success Metrics

### Performance
- [ ] Query response time: p95 < 200ms
- [ ] Sync time for 1000 vCenters: < 3 hours
- [ ] API uptime: > 99.9%
- [ ] Cache hit rate: > 80%

### Scale
- [ ] 1000+ vCenters syncing successfully
- [ ] 1M+ VMs in database
- [ ] 2000+ concurrent users supported

### Operations
- [ ] Zero data loss
- [ ] Automated monitoring and alerting
- [ ] Documented runbooks
- [ ] Team trained

## Post-Migration Tasks

### Week 11-12: Optimization

1. Fine-tune based on production load
2. Implement additional monitoring
3. Optimize costs
4. Plan for future growth

### Ongoing

1. Monthly performance reviews
2. Quarterly capacity planning
3. Regular security audits
4. Continuous optimization

## Estimated Costs

### One-Time
- Migration effort: 8-12 weeks (team time)
- Testing and validation
- Training

### Recurring (Monthly)
- Infrastructure: $4,000-6,000
- Monitoring tools: $200-500
- Support and maintenance

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data loss during migration | High | Multiple backups, parallel run |
| Performance degradation | Medium | Load testing, gradual rollout |
| Sync failures | Medium | Queue retry logic, monitoring |
| Cost overrun | Low | Reserved instances, auto-scaling |
| Team knowledge gap | Medium | Training, documentation |

## Conclusion

This migration plan provides a structured approach to scaling vMiner from a single-server setup to a distributed architecture supporting 1000+ vCenters. The phased approach minimizes risk while ensuring a smooth transition.

**Key Success Factors:**
1. Thorough testing at each phase
2. Parallel run before cutover
3. Comprehensive monitoring
4. Clear rollback plan
5. Team training and documentation
