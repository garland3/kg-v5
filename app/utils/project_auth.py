from functools import lru_cache, wraps
from fastapi import HTTPException, Request, Depends, Query # Added Query
from sqlalchemy.orm import Session
from typing import Optional

from app.postgres_db import get_postgres_db
from app.models.postgres_models import Project
from app.utils.auth import is_user_in_group

def check_project_access(project_id: int, user_email: str, db: Session) -> bool:
    """
    Check if a user has access to a project.
    
    Args:
        project_id: The ID of the project to check
        user_email: The email of the user
        db: Database session
        
    Returns:
        bool: True if the user has access, False otherwise
    """
    # Query the project
    db_project = db.query(Project).filter(Project.id == project_id).first()
    
    # If project doesn't exist, return False
    if not db_project:
        return False
    
    # Check if user is the creator
    if db_project.creator_email == user_email:
        return True
    
    # Check if user is in the project's authorization group
    if is_user_in_group(user_email, db_project.authorization_group):
        return True
    
    # User doesn't have access
    return False

# Cache the project access check to avoid repeated database queries
@lru_cache(maxsize=1024)
def cached_check_project_access(project_id: int, user_email: str) -> bool:
    """
    Cached version of check_project_access.
    
    Note: This function creates its own database session, so it should not be used
    within an existing database transaction.
    """
    from app.postgres_db import SessionLocal
    
    db = SessionLocal()
    try:
        return check_project_access(project_id, user_email, db)
    finally:
        db.close()

def require_project_access(project_id_param: str = "project_id"):
    """
    Decorator to require project access for a route.
    
    Args:
        project_id_param: The name of the path parameter that contains the project ID
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request = None, db: Session = None, **kwargs):
            # Get request and db from kwargs if not provided as args
            if request is None:
                request = kwargs.get("request")
            if db is None:
                db = kwargs.get("db")
            
            # Get project_id from path parameters
            project_id = kwargs.get(project_id_param)
            if project_id is None:
                # If project_id is not in path parameters, check if it's in the session
                project_id = request.session.get("selected_project_id")
                if project_id is None:
                    raise HTTPException(status_code=400, detail="Project ID not provided")
            
            # Get user email from request state
            user_email = request.state.user_email
            
            # Check if user has access to the project
            if not check_project_access(project_id, user_email, db):
                raise HTTPException(status_code=403, detail="You don't have access to this project")
            
            # User has access, proceed with the route
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator

# Dependency to check project access, prioritizing query param over session
async def verify_project_access(
    request: Request,
    project_id_query: Optional[int] = None,
    db: Session = Depends(get_postgres_db)
):
    """
    Dependency to check if a user has access to a project.
    Prioritizes project_id from query parameter, falls back to session.
    
    Args:
        request: The request object
        project_id_query: Project ID from query parameter (e.g., ?project_id=1)
        db: Database session
        
    Returns:
        dict: Project information if the user has access
        
    Raises:
        HTTPException: If the user doesn't have access to the project
    """
    # Get user email from request state
    user_email = request.state.user_email
    
    # Determine the project ID: prioritize query parameter, then session
    target_project_id = project_id_query

    # If called as a dependency, project_id_query will be set by FastAPI.
    # If called directly, project_id_query will be None, so check request.query_params.
    if target_project_id is None:
        project_id_param = request.query_params.get("project_id")
        if project_id_param is not None:
            try:
                target_project_id = int(project_id_param)
            except (ValueError, TypeError) as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid Project ID format. Received: {project_id_param}. Error: {str(e)}"
                )
        else:
            target_project_id = request.session.get("selected_project_id")
            if target_project_id is None:
                raise HTTPException(status_code=400, detail="Project ID not provided in query parameter or session")
    
    # Validate project_id format
    if not isinstance(target_project_id, int):
        try:
            target_project_id = int(target_project_id)
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid Project ID format. Received: {target_project_id}. Error: {str(e)}"
            )

    # Check if user has access to the project
    if not check_project_access(target_project_id, user_email, db):
        raise HTTPException(status_code=403, detail="You don't have access to this project")
    
    # Get project details
    db_project = db.query(Project).filter(Project.id == target_project_id).first()
    
    # If project doesn't exist (might happen if ID is invalid despite check_project_access passing somehow)
    if not db_project:
         raise HTTPException(status_code=404, detail="Project not found")
         
    # Return project information
    return {
        "project_id": db_project.id,
        "project_name": db_project.name,
        "project_description": db_project.description,
        "project_authorization_group": db_project.authorization_group,
        "project_creator_email": db_project.creator_email
    }

# Function to invalidate the cache for a specific project and user
def invalidate_project_access_cache(project_id: int, user_email: str):
    """
    Invalidate the cache for a specific project and user.
    
    Args:
        project_id: The ID of the project
        user_email: The email of the user
    """
    if (project_id, user_email) in cached_check_project_access.cache_info().currsize:
        cached_check_project_access.cache_clear()
