import time
import logging
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

class Neo4jDriver:
    def __init__(self):
        # Configure driver with a max retry time
        self.driver = GraphDatabase.driver(
            NEO4J_URI, 
            auth=(NEO4J_USER, NEO4J_PASSWORD),
            max_connection_lifetime=3600  # 1 hour in seconds
        )
        # Test connection when initializing
        self._test_connection()

    def _test_connection(self, max_attempts=3, retry_delay=1):
        attempt = 0
        last_error = None
        
        while attempt < max_attempts:
            try:
                self.driver.verify_connectivity()
                return True
            except ServiceUnavailable as e:
                attempt += 1
                last_error = e
                if attempt < max_attempts:
                    logging.debug(f"Connection test attempt {attempt}/{max_attempts} failed: {e}")
                    time.sleep(retry_delay)
        
        logging.warning(f"Failed to connect to Neo4j during driver init: {last_error}")
        return False

    def close(self):
        self.driver.close()

    def get_session(self):
        return self.driver.session()

# Dependency to get Neo4j session
def get_db():
    db = Neo4jDriver()
    try:
        yield db
    finally:
        db.close()

# Initialize the database with constraints
async def init_db():
    db = Neo4jDriver()
    max_attempts = 20
    retry_delay = 3  # seconds
    attempt = 0
    
    while attempt < max_attempts:
        try:
            with db.get_session() as session:
                # Create a uniqueness constraint on email
                # This prevents duplicate emails but allows null emails
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.email IS UNIQUE")
                logging.info("Successfully connected to Neo4j and created constraints")
                break
        except ServiceUnavailable as e:
            attempt += 1
            if attempt < max_attempts:
                logging.warning(f"Neo4j connection attempt {attempt}/{max_attempts} failed: {e}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logging.error(f"Failed to connect to Neo4j after {max_attempts} attempts: {e}")
                # Continue with application startup even if we can't connect to Neo4j
                # This allows the FastAPI app to start and show appropriate errors later
    db.close()
