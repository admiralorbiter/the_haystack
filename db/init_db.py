"""
Database initialization script.
Idempotent script to apply migrations to head and ensure db structure is created.
"""
import sys
import os

from alembic.config import Config
from alembic import command

def init_db():
    print("Running database initialization...")
    
    # Define paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_ini_path = os.path.join(base_dir, "alembic.ini")
    db_dir = os.path.join(base_dir, "db")
    
    # Ensure the db directory exists before running migrations
    os.makedirs(db_dir, exist_ok=True)

    # Trigger Alembic upgrade
    alembic_cfg = Config(alembic_ini_path)
    # We must point alembic to the script location explicitly if running from python
    alembic_cfg.set_main_option("script_location", os.path.join(base_dir, "migrations"))
    
    try:
        command.upgrade(alembic_cfg, "head")
        print("Database schema upgraded successfully.")
    except Exception as e:
        print(f"Error during migration: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    init_db()
