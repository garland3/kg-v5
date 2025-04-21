from fastapi import FastAPI, Request, Response, Depends
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
import logging
from app.database import init_db
from app.postgres_db import init_postgres_db
from app.routes import web, api, kg, deduplicate, postgres, projects, session
from app.config import USE_HEADER_AUTH, TEST_USER_EMAIL, TEST_USER_BELONGS_TO_AUTHORIZATION_GROUP

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
    logging.info("Application startup complete")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
