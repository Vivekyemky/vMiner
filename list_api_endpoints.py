"""
List All vMiner API Endpoints
Shows all available API endpoints with their methods and descriptions.

Author: Vivek Yemky <vivek.yemky@gmail.com>
"""

import requests
import json

def list_all_endpoints():
    """Fetch and display all API endpoints from OpenAPI schema."""
    
    try:
        # Fetch OpenAPI schema
        response = requests.get('http://localhost:8000/openapi.json')
        response.raise_for_status()
        
        openapi_spec = response.json()
        paths = openapi_spec.get('paths', {})
        
        print("=" * 100)
        print("vMiner API - All Available Endpoints")
        print("=" * 100)
        print(f"\nTotal Endpoints: {len(paths)}")
        print(f"API Version: {openapi_spec.get('info', {}).get('version', 'Unknown')}")
        print(f"API Title: {openapi_spec.get('info', {}).get('description', 'Unknown')}")
        print("\n" + "=" * 100)
        
        # Group endpoints by category
        categories = {
            'Authentication': [],
            'vCenter Management': [],
            'Inventory Queries': [],
            'Natural Language': [],
            'Data Export': [],
            'Statistics': [],
            'Settings & Scheduler': [],
            'Snapshots': [],
            'Resource Pools': [],
            'Networking': [],
            'Templates': [],
            'Storage': [],
            'DRS Rules': [],
            'Performance': [],
            'Monitoring': [],
            'Organization': [],
            'Security': [],
        }
        
        # Categorize endpoints
        for path, methods in paths.items():
            for method, details in methods.items():
                summary = details.get('summary', 'No description')
                
                # Determine category (default to Inventory Queries)
                category = 'Inventory Queries'
                
                if '/auth/' in path:
                    category = 'Authentication'
                elif '/vcenters' in path:
                    category = 'vCenter Management'
                elif '/query/chat' in path:
                    category = 'Natural Language'
                elif '/export/' in path:
                    category = 'Data Export'
                elif '/stats' in path:
                    category = 'Statistics'
                elif '/settings' in path or '/scheduler' in path:
                    category = 'Settings & Scheduler'
                elif '/snapshots' in path:
                    category = 'Snapshots'
                elif '/resource-pools' in path:
                    category = 'Resource Pools'
                elif '/port-groups' in path or '/dvs' in path:
                    category = 'Networking'
                elif '/templates' in path:
                    category = 'Templates'
                elif '/storage-adapters' in path or '/scsi-luns' in path:
                    category = 'Storage'
                elif '/drs-rules' in path:
                    category = 'DRS Rules'
                elif '/performance/' in path:
                    category = 'Performance'
                elif '/events' in path or '/alarms' in path:
                    category = 'Monitoring'
                elif '/folders' in path or '/vapps' in path:
                    category = 'Organization'
                elif '/permissions' in path:
                    category = 'Security'
                
                categories[category].append({
                    'method': method.upper(),
                    'path': path,
                    'summary': summary
                })
        
        # Display endpoints by category
        for category, endpoints in categories.items():
            if endpoints:
                print(f"\n{'─' * 100}")
                print(f"📁 {category} ({len(endpoints)} endpoints)")
                print('─' * 100)
                
                for endpoint in sorted(endpoints, key=lambda x: x['path']):
                    method_color = {
                        'GET': '🔍',
                        'POST': '➕',
                        'PUT': '✏️',
                        'DELETE': '🗑️'
                    }.get(endpoint['method'], '📌')
                    
                    print(f"{method_color} {endpoint['method']:6s} {endpoint['path']:50s} - {endpoint['summary']}")
        
        print("\n" + "=" * 100)
        print("\n💡 To test these endpoints:")
        print("   1. Visit: http://localhost:8000/docs (Swagger UI)")
        print("   2. Visit: http://localhost:8000/redoc (ReDoc)")
        print("   3. Use curl, Postman, or any HTTP client")
        print("\n🔐 Authentication:")
        print("   Most endpoints require JWT token from POST /api/auth/login")
        print("   Add header: Authorization: Bearer <your_token>")
        print("\n" + "=" * 100)
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to API server")
        print("   Make sure the server is running: uvicorn main:app --reload")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    list_all_endpoints()
