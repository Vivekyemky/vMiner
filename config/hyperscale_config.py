# Configuration for distributed PostgreSQL setup

# Primary database (for writes - sync operations)
PRIMARY_DATABASE_URL = "postgresql://user:password@primary-db-host:5432/vminer"

# Read replicas (for queries - API operations)
# The system will round-robin between these for read operations
READ_REPLICA_URLS = [
    "postgresql://user:password@replica1-db-host:5432/vminer",
    "postgresql://user:password@replica2-db-host:5432/vminer",
    "postgresql://user:password@replica3-db-host:5432/vminer",
]

# Redis cache configuration
REDIS_HOST = "redis-cluster-host"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = "your-redis-password"

# Cache TTL (seconds)
CACHE_TTL_SHORT = 300      # 5 minutes - for frequently changing data
CACHE_TTL_MEDIUM = 1800    # 30 minutes - for semi-static data
CACHE_TTL_LONG = 3600      # 1 hour - for static data

# RabbitMQ configuration (for distributed sync)
RABBITMQ_HOST = "rabbitmq-host"
RABBITMQ_PORT = 5672
RABBITMQ_USER = "vminer"
RABBITMQ_PASSWORD = "your-rabbitmq-password"
RABBITMQ_VHOST = "vminer"

# Sync worker configuration
SYNC_WORKERS_PER_INSTANCE = 10  # Number of concurrent vCenter connections per worker
TOTAL_SYNC_WORKERS = 100        # Total across all worker instances

# API configuration
API_WORKERS = 16                # Uvicorn workers per API instance
MAX_CONCURRENT_REQUESTS = 1000  # Per API instance

# Performance tuning
ENABLE_QUERY_CACHE = True
ENABLE_CONNECTION_POOLING = True
DB_POOL_SIZE = 50
DB_MAX_OVERFLOW = 100
