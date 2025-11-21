"""
Verify Database Tables
Checks that all 26 tables were created successfully in the SQLite database.

Author: Vivek Yemky <vivek.yemky@gmail.com>
"""

import sqlite3
import os

def verify_database():
    """Verify all expected tables exist in the database."""
    
    db_path = 'inventory.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Database file '{db_path}' not found!")
        print("   Please run the API first to create the database.")
        return False
    
    # Expected tables
    expected_tables = [
        # Original tables
        'vcenters',
        'virtual_machines',
        'hosts',
        'datastores',
        'clusters',
        
        # Networking
        'distributed_vswitches',
        'standard_vswitches',
        'port_groups',
        'network_adapters',
        
        # Storage
        'storage_adapters',
        'scsi_luns',
        
        # Resource Management
        'resource_pools',
        'vapps',
        'folders',
        
        # Snapshots & Templates
        'snapshots',
        'vm_templates',
        'content_libraries',
        
        # Configuration
        'drs_rules',
        
        # Performance
        'vm_performance',
        'host_performance',
        
        # Monitoring
        'events',
        'alarms',
        'tasks',
        
        # Security & Metadata
        'permissions',
        'custom_attributes',
        'tags'
    ]
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        actual_tables = [row[0] for row in cursor.fetchall()]
        
        print("=" * 70)
        print("vMiner Database Verification")
        print("=" * 70)
        print(f"\nDatabase: {db_path}")
        print(f"Total tables found: {len(actual_tables)}")
        print(f"Expected tables: {len(expected_tables)}")
        
        # Check for missing tables
        missing_tables = set(expected_tables) - set(actual_tables)
        extra_tables = set(actual_tables) - set(expected_tables)
        
        if not missing_tables and not extra_tables:
            print("\n✅ SUCCESS! All tables created successfully!\n")
        else:
            print("\n⚠️  WARNING: Table mismatch detected!\n")
        
        # Display results
        print("\n📊 Table Status:")
        print("-" * 70)
        
        # Group tables by category
        categories = {
            'Core Tables': ['vcenters', 'virtual_machines', 'hosts', 'datastores', 'clusters'],
            'Networking': ['distributed_vswitches', 'standard_vswitches', 'port_groups', 'network_adapters'],
            'Storage': ['storage_adapters', 'scsi_luns'],
            'Resource Management': ['resource_pools', 'vapps', 'folders'],
            'Snapshots & Templates': ['snapshots', 'vm_templates', 'content_libraries'],
            'Configuration': ['drs_rules'],
            'Performance': ['vm_performance', 'host_performance'],
            'Monitoring': ['events', 'alarms', 'tasks'],
            'Security & Metadata': ['permissions', 'custom_attributes', 'tags']
        }
        
        for category, tables in categories.items():
            print(f"\n{category}:")
            for table in tables:
                if table in actual_tables:
                    # Get row count
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"  ✅ {table:30s} ({count:,} rows)")
                else:
                    print(f"  ❌ {table:30s} (MISSING)")
        
        if missing_tables:
            print(f"\n❌ Missing tables: {', '.join(sorted(missing_tables))}")
        
        if extra_tables:
            print(f"\n➕ Extra tables: {', '.join(sorted(extra_tables))}")
        
        print("\n" + "=" * 70)
        
        conn.close()
        return len(missing_tables) == 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = verify_database()
    exit(0 if success else 1)
