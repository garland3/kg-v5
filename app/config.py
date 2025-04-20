import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Neo4j connection configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

# PostgreSQL connection configuration
POSTGRES_URI = os.getenv("POSTGRES_URI", "postgresql://postgres:postgres123@localhost:5432/app_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
POSTGRES_DB = os.getenv("POSTGRES_DB", "app_db")

# Authentication configuration
USE_HEADER_AUTH = os.getenv("USE_HEADER_AUTH", "false").lower() == "true"
TEST_USER_EMAIL = os.getenv("TEST_USER_EMAIL", "test@example.com")
TEST_USER_BELONGS_TO_AUTHORIZATION_GROUP = os.getenv("TEST_USER_BELONGS_TO_AUTHORIZATION_GROUP", "TEST_USERS")
