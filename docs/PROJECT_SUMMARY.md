# vMiner - Project Summary

## Overview
**vMiner** is an enterprise-grade REST API for managing and querying VMware vCenter inventory data across 100+ vCenter instances. Built with FastAPI and Python, it provides intelligent natural language querying, concurrent data synchronization, and comprehensive export capabilities.

## Key Features

### ✅ Multi-vCenter Support
- Connects to 100+ vCenter instances concurrently
- Thread-pool based synchronization (configurable workers)
- Individual or bulk sync operations
- Real-time sync status tracking

### ✅ Intelligent Chat Interface
- Natural language query processing
- **Fuzzy matching** for spelling correction (using RapidFuzz)
- Intent recognition (Get, Count, List, Show)
- Context-aware follow-up queries
- Handles typos and variations automatically

### ✅ Comprehensive Inventory Data
- **Virtual Machines**: Power state, CPU, memory, IP, OS, cluster, host
- **Hosts**: Connection state, resources, VM count, cluster
- **Datastores**: Capacity, free space, type, VM count
- **Clusters**: DRS/HA status, resource totals, host/VM counts

### ✅ Export Capabilities
- CSV export
- Excel export (XLSX)
- JSON export
- Direct download via API

### ✅ Background Scheduler
- Periodic automatic synchronization
- Configurable sync intervals
- Start/stop controls via API
- Independent of manual sync operations

### ✅ Enterprise-Ready
- JWT-based authentication
- CORS support for web integration
- Comprehensive error handling and logging
- SQLite for caching (PostgreSQL-ready)
- Concurrent connection handling

## Project Structure

```
vMiner/
├── backend/
│   ├── __init__.py
│   ├── db_manager.py          # Database management & models
│   ├── vcenter_client.py      # vCenter connection & data retrieval
│   ├── sync_engine.py         # Concurrent sync orchestration
│   └── query_engine.py        # Natural language query parser
├── utils/
│   ├── __init__.py
│   ├── export_utils.py        # CSV/Excel/JSON export
│   └── scheduler.py           # Background sync scheduler
├── api/                       # (Reserved for future API versioning)
├── models/                    # (Reserved for additional models)
├── exports/                   # Generated export files
├── main.py                    # FastAPI application
├── setup.py                   # Database initialization script
├── requirements.txt           # Python dependencies
├── .env.example               # Environment configuration template
├── .gitignore                 # Git ignore rules
├── README.md                  # Project overview
├── QUICKSTART.md              # Quick start guide
├── ENTERPRISE_RECOMMENDATIONS.md  # Enterprise best practices
└── vMiner_Postman_Collection.json  # API testing collection
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Framework** | FastAPI | High-performance async API |
| **VMware SDK** | pyvmomi | vCenter connectivity |
| **Database** | SQLAlchemy + SQLite | Local inventory cache |
| **Source DB** | SQLAlchemy (MSSQL/PostgreSQL) | vCenter list source |
| **NLP** | RapidFuzz | Spelling correction |
| **Export** | Pandas + OpenPyXL | Data export |
| **Auth** | PyJWT | Token-based authentication |
| **Scheduler** | APScheduler | Background sync jobs |
| **Concurrency** | ThreadPoolExecutor | Parallel vCenter connections |

## API Endpoints

### Authentication
- `POST /api/auth/login` - Get JWT token
- `POST /api/auth/logout` - Invalidate session

### vCenter Management
- `GET /api/vcenters` - List all vCenters
- `POST /api/vcenters/sync` - Trigger sync (all or specific)
- `GET /api/vcenters/{id}/status` - Get sync status

### Chat Queries
- `POST /api/query/chat` - Natural language query

### Inventory
- `GET /api/vms` - List VMs (with filters)
- `GET /api/hosts` - List hosts (with filters)
- `GET /api/datastores` - List datastores (with filters)
- `GET /api/clusters` - List clusters

### Export
- `POST /api/export/csv` - Export to CSV
- `POST /api/export/json` - Export to JSON
- `POST /api/export/excel` - Export to Excel

### Settings
- `GET /api/settings` - Get current settings
- `PUT /api/settings/sync-interval` - Update sync interval
- `POST /api/settings/scheduler/start` - Start auto-sync
- `POST /api/settings/scheduler/stop` - Stop auto-sync

### Statistics
- `GET /api/stats` - Get inventory statistics

## Query Examples

The chat interface understands natural language with spelling tolerance:

| Query | What it does |
|-------|-------------|
| `get all powered on VMs` | Returns all running VMs |
| `show me hosts with no vms` | Returns hosts with 0 VMs |
| `get all empty datastores` | Returns datastores with no VMs |
| `list vms in cluster Production` | Returns VMs in specific cluster |
| `count powered off vms` | Returns count of stopped VMs |

**Spelling tolerance examples:**
- `shoe me all powred on vms` → Corrects to "show me all powered on vms"
- `get all emty datastors` → Corrects to "get all empty datastores"

## Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create `.env` file:
```env
SQL_CONNECTION_STRING=mssql+pymssql://user:pass@server/database
SECRET_KEY=your-secret-key
SYNC_INTERVAL_MINUTES=60
```

### 3. Initialize Database
```bash
python setup.py
```

### 4. Run API
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Access Documentation
Open: `http://localhost:8000/docs`

## Integration Example

### JavaScript/TypeScript
```javascript
// Login
const response = await fetch('http://localhost:8000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin', password: 'admin' })
});
const { access_token } = await response.json();

// Query
const queryResponse = await fetch('http://localhost:8000/api/query/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${access_token}`
  },
  body: JSON.stringify({ query: 'get all powered on VMs' })
});
const results = await queryResponse.json();
```

### Python
```python
import requests

# Login
r = requests.post('http://localhost:8000/api/auth/login',
                  json={'username': 'admin', 'password': 'admin'})
token = r.json()['access_token']

# Query
headers = {'Authorization': f'Bearer {token}'}
r = requests.post('http://localhost:8000/api/query/chat',
                  headers=headers,
                  json={'query': 'get all powered on VMs'})
print(r.json())
```

## Performance Characteristics

### Scalability
- **100 vCenters**: ~10-30 minutes initial sync (with 10 workers)
- **10,000 VMs**: ~2-5 seconds query time (cached)
- **Concurrent requests**: Supports 100+ simultaneous API calls

### Resource Usage
- **Memory**: ~200-500 MB (depends on inventory size)
- **Disk**: ~100 MB per 10,000 VMs (SQLite)
- **CPU**: Scales with worker count (default: 10 threads)

## Security Considerations

### Current Implementation
- JWT-based authentication (24-hour expiry)
- Bearer token authorization
- CORS enabled (configure for production)

### Production Recommendations
1. Use strong SECRET_KEY (256-bit random)
2. Enable HTTPS (reverse proxy with SSL)
3. Implement rate limiting
4. Add IP whitelisting
5. Use HashiCorp Vault for vCenter credentials
6. Enable audit logging
7. Implement RBAC (role-based access control)

## Enterprise Enhancements

See `ENTERPRISE_RECOMMENDATIONS.md` for detailed recommendations including:
- Migration to PostgreSQL
- Redis caching layer
- High availability setup
- Monitoring with Prometheus/Grafana
- AI/ML integration
- Advanced analytics
- Third-party integrations

## Deployment Options

### Option 1: Single Server
- Run on Windows/Linux server
- Use systemd/Windows Service for auto-start
- NGINX reverse proxy for SSL

### Option 2: Containerized (Docker)
```dockerfile
FROM python:3.10
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Option 3: Cloud (AWS/Azure)
- EC2/VM instances
- RDS for database
- Load balancer for HA
- Auto-scaling groups

## Maintenance

### Daily
- Monitor sync status
- Check error logs
- Verify API health

### Weekly
- Review query performance
- Check database size
- Update vCenter credentials if needed

### Monthly
- Backup database
- Update dependencies
- Review security logs

## Troubleshooting

### Common Issues

**Issue**: Sync fails for specific vCenter
- **Solution**: Check credentials, network connectivity, firewall rules

**Issue**: Slow query performance
- **Solution**: Add database indexes, increase cache size, migrate to PostgreSQL

**Issue**: High memory usage
- **Solution**: Reduce worker count, implement pagination, clear old data

## Future Roadmap

### Phase 1 (Completed)
- ✅ Core API implementation
- ✅ Natural language queries
- ✅ Multi-vCenter sync
- ✅ Export functionality

### Phase 2 (Recommended)
- [ ] PostgreSQL migration
- [ ] Redis caching
- [ ] Advanced filters
- [ ] Webhook support

### Phase 3 (Advanced)
- [ ] AI-powered query suggestions
- [ ] Anomaly detection
- [ ] Predictive analytics
- [ ] Mobile app

## Support & Documentation

- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Quick Start**: QUICKSTART.md
- **Enterprise Guide**: ENTERPRISE_RECOMMENDATIONS.md
- **Postman Collection**: vMiner_Postman_Collection.json

## License

[Specify your license here]

## Contributors

[Add contributors here]

---

**Built for enterprise-scale VMware environments**
