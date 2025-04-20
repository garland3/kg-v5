import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from app.config import POSTGRES_URI

# Create SQLAlchemy Base class for models
Base = declarative_base()

class PostgresDriver:
    def __init__(self):
        # Configure SQLAlchemy engine with connection pool settings
        self.engine = create_engine(
            POSTGRES_URI,
            pool_pre_ping=True,  # Verify connections before using them
            pool_recycle=3600,   # Recycle connections after 1 hour
            echo=False           # Set to True for SQL query logging
        )
        # Test connection when initializing
        self._test_connection()
        
        # Create session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def _test_connection(self, max_attempts=3, retry_delay=1):
        attempt = 0
        last_error = None
        
        while attempt < max_attempts:
            try:
                # Test connection with a simple query
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return True
            except OperationalError as e:
                attempt += 1
                last_error = e
                if attempt < max_attempts:
                    logging.debug(f"PostgreSQL connection test attempt {attempt}/{max_attempts} failed: {e}")
                    time.sleep(retry_delay)
        
        logging.warning(f"Failed to connect to PostgreSQL during driver init: {last_error}")
        return False

    def close(self):
        self.engine.dispose()

    def get_session(self):
        db_session = self.SessionLocal()
        try:
            return db_session
        finally:
            db_session.close()

# Dependency to get PostgreSQL session
def get_postgres_db():
    db = PostgresDriver()
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        db.close()

# Initialize the database with tables
async def init_postgres_db():
    db = PostgresDriver()
    max_attempts = 20
    retry_delay = 3  # seconds
    attempt = 0
    
    while attempt < max_attempts:
        try:
            # Create all tables defined in models
            Base.metadata.create_all(bind=db.engine)
            logging.info("Successfully connected to PostgreSQL and created tables")
            break
        except OperationalError as e:
            attempt += 1
            if attempt < max_attempts:
                logging.warning(f"PostgreSQL connection attempt {attempt}/{max_attempts} failed: {e}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logging.error(f"Failed to connect to PostgreSQL after {max_attempts} attempts: {e}")
                # Continue with application startup even if we can't connect to PostgreSQL
                # This allows the FastAPI app to start and show appropriate errors later
    db.close()
