from fastapi import FastAPI, Request, Response, Depends
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
import logging
from app.database import init_db
from app.postgres_db import init_postgres_db
from app.routes import web, api, kg, deduplicate, postgres, projects, session
from app.config import USE_HEADER_AUTH, TEST_USER_EMAIL, TEST_USER_BELONGS_TO_AUTHORIZATION_GROUP

import os
from neo4j import GraphDatabase

from src.kg.deduplicate import batch_generate_embeddings

# Vector index creation for Neo4j
def get_embedding_dimensions(model_name):
    # Known OpenAI embedding model dimensions
    model_dims = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536
    }
    # Try to match by substring for flexibility
    for key, val in model_dims.items():
        if key in model_name:
            return val
    return 1536  # Default

async def create_vector_index():
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
    embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    dimensions = get_embedding_dimensions(embedding_model)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            session.run(
                """
                CREATE VECTOR INDEX person_embeddings IF NOT EXISTS
                FOR (p:Person) ON (p.embedding)
                OPTIONS {indexConfig: {
                  `vector.dimensions`: $dimensions,
                  `vector.similarity_function`: 'cosine'
                }}
                """,
                dimensions=dimensions
            )
    finally:
        driver.close()

# Create FastAPI app
app = FastAPI(title="Neo4j FastAPI Demo")

# User authentication middleware
class UserAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Get user email from header or use test email based on config
        if USE_HEADER_AUTH:
            if "X-user-email" not in request.headers:
                logging.warning("Missing X-user-email header")
                return Response(status_code=401, content="Unauthorized")
            
            user_email = request.headers.get("X-user-email")
            # if missing or non, then rediect to /login which will be handeled by another app using nginx or traefik
            if not user_email:
                logging.warning("Missing user email in header")
                return Response(status_code=401, content="Unauthorized")
            
        else:
            user_email = TEST_USER_EMAIL
        
        # Store user email in request state for access in route handlers
        request.state.user_email = user_email
        request.state.user_auth_group = TEST_USER_BELONGS_TO_AUTHORIZATION_GROUP
        
        # Process the request and get the response
        response = await call_next(request)
        return response


# Add middleware
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")  # Replace with a secure secret key
app.add_middleware(UserAuthMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(web.router)
app.include_router(api.router)
app.include_router(kg.router)
app.include_router(deduplicate.router)
app.include_router(postgres.router)
app.include_router(projects.router)
app.include_router(session.router)

# Startup event
@app.on_event("startup")
async def startup_db_client():
    await init_db()
    await init_postgres_db()
    await create_vector_index()
    await batch_generate_embeddings()
    logging.info("Application startup complete")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
