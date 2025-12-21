"""
============================================================================
Project Autonomous Alpha v1.3.2
Database Session - SQLAlchemy Engine & Session Management
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: PostgreSQL connection via app_trading role
Side Effects: Database connections

SOVEREIGN MANDATE:
- Connect using app_trading role (SELECT/INSERT only)
- No UPDATE/DELETE permissions at connection level
- Connection pooling for Hot Path performance

============================================================================
"""

import os
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

def get_database_url() -> str:
    """
    Construct PostgreSQL connection URL from environment variables.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Environment variables must be set
    Side Effects: Reads from environment
    
    Returns:
        str: PostgreSQL connection URL
        
    Environment Variables:
        DB_HOST: Database host (default: localhost)
        DB_PORT: Database port (default: 5432)
        DB_NAME: Database name (default: autonomous_alpha)
        DB_USER: Database user (default: app_trading)
        DB_PASSWORD: Database password (required)
    """
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "autonomous_alpha")
    user = os.getenv("DB_USER", "app_trading")
    password = os.getenv("DB_PASSWORD", "trading_app_2024")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


# ============================================================================
# SQLALCHEMY ENGINE
# ============================================================================

# Connection URL
DATABASE_URL = get_database_url()

# Create engine with connection pooling optimized for Hot Path
engine = create_engine(
    DATABASE_URL,
    # Connection pool settings for Hot Path performance
    poolclass=QueuePool,
    pool_size=10,           # Maintain 10 connections
    max_overflow=20,        # Allow up to 20 additional connections under load
    pool_timeout=30,        # Wait up to 30s for a connection
    pool_recycle=1800,      # Recycle connections after 30 minutes
    pool_pre_ping=True,     # Verify connections before use
    
    # Echo SQL for debugging (disable in production)
    echo=os.getenv("DB_ECHO", "false").lower() == "true",
    
    # Execution options
    execution_options={
        "isolation_level": "READ COMMITTED"
    }
)


# ============================================================================
# SESSION FACTORY
# ============================================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database session injection.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Creates and closes database session
    
    Yields:
        Session: SQLAlchemy database session
        
    Usage:
        @app.post("/signals")
        async def create_signal(db: Session = Depends(get_db)):
            ...
            
    SOVEREIGN MANDATE:
        - Session is automatically closed after request
        - Rollback on exception
        - Connection returned to pool
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ============================================================================
# CONNECTION EVENT LISTENERS
# ============================================================================

@event.listens_for(engine, "connect")
def set_search_path(dbapi_connection, connection_record):
    """
    Set search path on new connections.
    
    Reliability Level: STANDARD
    Input Constraints: None
    Side Effects: Sets PostgreSQL search_path
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO public")
    cursor.close()


@event.listens_for(engine, "connect")
def set_timezone(dbapi_connection, connection_record):
    """
    Ensure all connections use UTC timezone.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Sets PostgreSQL timezone
    
    SOVEREIGN MANDATE: All timestamps must be UTC
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("SET timezone TO 'UTC'")
    cursor.close()


# ============================================================================
# HEALTH CHECK
# ============================================================================

def check_database_connection() -> bool:
    """
    Verify database connectivity.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Executes test query
    
    Returns:
        bool: True if database is reachable
        
    Raises:
        Exception: If database connection fails
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        raise Exception(f"Database connection failed: {e}")


# ============================================================================
# END OF DATABASE SESSION MODULE
# ============================================================================
