"""
vMiner Setup Script
Initializes the local database and fetches vCenter connection details from SQL database.

Author: Vivek Yemky <vivek.yemky@gmail.com>
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from backend.db_manager import DatabaseManager

# Load environment variables
load_dotenv()

def main():
    """
    Main setup function to initialize database and fetch vCenter list.
    """
    print("=" * 60)
    print("vMiner - Database Setup")
    print("=" * 60)
    
    # Check for required environment variables
    sql_connection_string = os.getenv("SQL_CONNECTION_STRING")
    if not sql_connection_string:
        print("ERROR: SQL_CONNECTION_STRING not found in .env file")
        print("Please configure your .env file with the SQL database connection string")
        sys.exit(1)
    
    print("\n1. Initializing local database...")
    db_manager = DatabaseManager()
    print("   ✓ Local database initialized")
    
    print("\n2. Connecting to SQL database...")
    try:
        engine = create_engine(sql_connection_string)
        connection = engine.connect()
        print("   ✓ Connected to SQL database")
    except Exception as e:
        print(f"   ✗ Failed to connect to SQL database: {e}")
        sys.exit(1)
    
    print("\n3. Fetching vCenter list...")
    try:
        # IMPORTANT: Update this query to match your SQL database schema
        # Example schemas:
        # - SELECT hostname, username, password FROM vcenters WHERE is_active = 1
        # - SELECT server_name, user_name, pwd FROM vcenter_inventory WHERE enabled = 'Y'
        # - SELECT vc_host, vc_user, vc_pass FROM infrastructure WHERE type = 'vcenter'
        
        query = text("""
            SELECT 
                hostname,
                username,
                password
            FROM vcenters
            WHERE is_active = 1
        """)
        
        result = connection.execute(query)
        vcenters = result.fetchall()
        
        if not vcenters:
            print("   ⚠ No vCenters found in SQL database")
            print("   Please check your SQL query and database contents")
            connection.close()
            sys.exit(1)
        
        print(f"   ✓ Found {len(vcenters)} vCenter(s)")
        
    except Exception as e:
        print(f"   ✗ Failed to fetch vCenter list: {e}")
        print("\n   Please update the SQL query in setup.py to match your database schema")
        connection.close()
        sys.exit(1)
    
    print("\n4. Populating local database...")
    session = db_manager.get_local_session()
    
    from backend.db_manager import VCenter
    
    added_count = 0
    updated_count = 0
    
    for vc in vcenters:
        hostname, username, password = vc
        
        # Check if vCenter already exists
        existing = session.query(VCenter).filter(
            VCenter.hostname == hostname
        ).first()
        
        if existing:
            # Update existing
            existing.username = username
            existing.password = password
            existing.is_active = True
            updated_count += 1
        else:
            # Add new
            new_vcenter = VCenter(
                hostname=hostname,
                username=username,
                password=password,
                is_active=True
            )
            session.add(new_vcenter)
            added_count += 1
    
    session.commit()
    session.close()
    connection.close()
    
    print(f"   ✓ Added {added_count} new vCenter(s)")
    print(f"   ✓ Updated {updated_count} existing vCenter(s)")
    
    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Start the API: uvicorn main:app --reload")
    print("2. Access API docs: http://localhost:8000/docs")
    print("3. Trigger sync: POST /api/vcenters/sync")
    print("\n")

if __name__ == "__main__":
    main()
