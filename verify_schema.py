import os
import django
from django.db import connection
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')
django.setup()

def verify():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT s.name AS schema_name, t.name AS table_name
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = 'artemis_db'
            ORDER BY t.name;
        """)
        rows = cursor.fetchall()
        print("Tables in schema 'artemis_db':")
        for row in rows:
            print(f"{row[0]}.{row[1]}")
        
        expected_tables = [
            'ioc_entry', 'ioc_load_batch', 'ioc_load_result', 
            'ioc_tool', 'ioc_type', 'tool', 
            'tool_hash_type', 'tool_indicator_rule'
        ]
        
        found_tables = [row[1] for row in rows]
        missing = set(expected_tables) - set(found_tables)
        
        if missing:
            print(f"FAILED: Missing tables in 'artemis_db' schema: {missing}")
            # Check if they exist in dbo
            cursor.execute("""
                SELECT s.name, t.name 
                FROM sys.tables t 
                JOIN sys.schemas s ON t.schema_id = s.schema_id 
                WHERE t.name IN %s
            """, [tuple(missing)])
            found_elsewhere = cursor.fetchall()
            if found_elsewhere:
                print(f"Found missing tables in other schemas: {found_elsewhere}")
            exit(1)
        else:
            print("SUCCESS: All expected tables found in 'artemis_db'.")

if __name__ == "__main__":
    verify()
