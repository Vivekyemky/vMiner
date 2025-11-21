# Quick Start Guide - vMiner API

## Prerequisites
- Python 3.10 or higher
- Access to vCenter instances
- SQL database with vCenter connection details

## Installation

### 1. Clone or Navigate to Project
```bash
cd d:/Aim/projects/ai-ml/Infrastructure/vMiner
```

### 2. Create Virtual Environment
```bash
python -m venv venv
```

### 3. Activate Virtual Environment
**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

## Configuration

### 1. Create .env File
Copy the example and edit with your details:
```bash
copy .env.example .env
```

Edit `.env`:
```env
SQL_CONNECTION_STRING=mssql+pymssql://username:password@server/database
SECRET_KEY=your-super-secret-key-here-change-this
SYNC_INTERVAL_MINUTES=60
```

### 2. Update SQL Query in setup.py
Open `setup.py` and modify the SQL query to match your database schema:
```python
query = text("""
    SELECT 
        hostname,
        username,
        password
    FROM your_vcenter_table
    WHERE is_active = 1
""")
```

### 3. Initialize Database
```bash
python setup.py
```

This will:
- Create the local SQLite database
- Fetch vCenter list from your SQL database
- Populate the local database

## Running the API

### Development Mode
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## First Steps

### 1. Access API Documentation
Open your browser and navigate to:
```
http://localhost:8000/docs
```

This will show the interactive Swagger UI.

### 2. Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

**Save this token!** You'll need it for all subsequent requests.

### 3. Check vCenters
```bash
curl -X GET http://localhost:8000/api/vcenters \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### 4. Trigger Initial Sync
```bash
curl -X POST http://localhost:8000/api/vcenters/sync \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{}'
```

This will start syncing all vCenters in the background. For 100+ vCenters, this may take 10-30 minutes.

### 5. Check Sync Status
```bash
curl -X GET http://localhost:8000/api/vcenters \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

Look for `sync_status` field:
- `pending`: Not started
- `syncing`: In progress
- `completed`: Successfully synced
- `failed`: Error occurred

### 6. View Statistics
```bash
curl -X GET http://localhost:8000/api/stats \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Using the Chat Interface

### Example Queries

**Get all powered on VMs:**
```bash
curl -X POST http://localhost:8000/api/query/chat \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "get all powered on VMs"}'
```

**Get hosts with no VMs:**
```bash
curl -X POST http://localhost:8000/api/query/chat \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "show me hosts with no vms"}'
```

**Get empty datastores:**
```bash
curl -X POST http://localhost:8000/api/query/chat \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "get all empty datastores"}'
```

**The chat engine handles spelling mistakes:**
```bash
curl -X POST http://localhost:8000/api/query/chat \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "shoe me all powred on vms"}'
```

## Exporting Data

### Export to CSV
```bash
curl -X POST http://localhost:8000/api/export/csv \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "get all powered on VMs"}' \
  --output report.csv
```

### Export to Excel
```bash
curl -X POST http://localhost:8000/api/export/excel \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "get all hosts"}' \
  --output report.xlsx
```

### Export to JSON
```bash
curl -X POST http://localhost:8000/api/export/json \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "get all datastores"}' \
  --output report.json
```

## Scheduler Management

### Start Automatic Sync
```bash
curl -X POST http://localhost:8000/api/settings/scheduler/start \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Stop Automatic Sync
```bash
curl -X POST http://localhost:8000/api/settings/scheduler/stop \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Update Sync Interval
```bash
curl -X PUT "http://localhost:8000/api/settings/sync-interval?interval_minutes=30" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Integration with Your Portal

### JavaScript Example
```javascript
// Login
const loginResponse = await fetch('http://localhost:8000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin', password: 'admin' })
});
const { access_token } = await loginResponse.json();

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
console.log(results);
```

### Python Example
```python
import requests

# Login
response = requests.post(
    'http://localhost:8000/api/auth/login',
    json={'username': 'admin', 'password': 'admin'}
)
token = response.json()['access_token']

# Query
headers = {'Authorization': f'Bearer {token}'}
response = requests.post(
    'http://localhost:8000/api/query/chat',
    headers=headers,
    json={'query': 'get all powered on VMs'}
)
print(response.json())
```

## Troubleshooting

### Issue: "Failed to connect to vCenter"
- Check vCenter credentials in database
- Verify network connectivity
- Check firewall rules

### Issue: "SQL connection failed"
- Verify SQL_CONNECTION_STRING in .env
- Check SQL server accessibility
- Verify credentials

### Issue: "No data returned"
- Run sync first: `POST /api/vcenters/sync`
- Check sync status: `GET /api/vcenters`
- View logs for errors

### Issue: "Token expired"
- Login again to get new token
- Tokens expire after 24 hours by default

## Next Steps

1. **Secure the API**: Update SECRET_KEY, implement proper authentication
2. **Configure CORS**: Update allowed origins in main.py
3. **Enable HTTPS**: Use reverse proxy (NGINX) with SSL certificate
4. **Monitor**: Set up logging and monitoring
5. **Scale**: Deploy multiple instances behind load balancer

## Support

For issues or questions, check:
- API Documentation: http://localhost:8000/docs
- Enterprise Recommendations: ENTERPRISE_RECOMMENDATIONS.md
- README: README.md
