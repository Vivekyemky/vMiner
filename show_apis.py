"""
Quick API Endpoint Lister
Simple script to show all vMiner API endpoints.
"""

import requests

try:
    response = requests.get('http://localhost:8001/openapi.json', timeout=5)
    spec = response.json()
    paths = spec.get('paths', {})
    
    print("\n" + "="*80)
    print(f"vMiner API - All {len(paths)} Endpoints")
    print("="*80 + "\n")
    
    for path in sorted(paths.keys()):
        methods = list(paths[path].keys())
        for method in methods:
            summary = paths[path][method].get('summary', '')
            print(f"{method.upper():6s} {path:45s} {summary}")
    
    print("\n" + "="*80)
    print("Visit http://localhost:8001/docs for interactive documentation")
    print("="*80 + "\n")
    
except Exception as e:
    print(f"Error: {e}")
    print("Make sure the API server is running!")
