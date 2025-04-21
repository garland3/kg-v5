from fastapi import APIRouter, HTTPException, Depends, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.postgres_db import get_postgres_db
from app.models.postgres_models import Project, KnowledgeGraph
from app.utils.auth import check_user_authorization_groups, is_user_in_group

router = APIRouter(
    prefix="/api/projects",
    tags=["projects"],
    responses={404: {"description": "Not found"}},
)

# Pydantic models for request/response
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    authorization_group: str

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    creator_email: str
    authorization_group: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    authorization_group: Optional[str] = None

# Project routes
@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project: ProjectCreate, request: Request, db: Session = Depends(get_postgres_db)):
    """Create a new project"""
    # Get user email from request state
    user_email = request.state.user_email
    
    # Create project
    db_project = Project(
        name=project.name,
        description=project.description,
        creator_email=user_email,
        authorization_group=project.authorization_group
    )
    
    try:
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error creating project"
        )

@router.get("/", response_model=List[ProjectResponse])
def read_projects(request: Request, db: Session = Depends(get_postgres_db)):
    """Get a list of projects that the user has access to"""
    # Get user email from request state
    user_email = request.state.user_email
    
    # Get user's authorization groups from the mock external service
    user_auth_groups = check_user_authorization_groups(user_email)
    
    # Query all projects
    all_projects = db.query(Project).all()
    
    # Filter projects where user is creator or in the authorization group
    accessible_projects = []
    for project in all_projects:
        if project.creator_email == user_email or project.authorization_group in user_auth_groups:
            accessible_projects.append(project)
    
    return accessible_projects

@router.get("/{project_id}", response_model=ProjectResponse)
def read_project(project_id: int, request: Request, db: Session = Depends(get_postgres_db)):
    """Get a specific project by ID"""
    # Get user email from request state
    user_email = request.state.user_email
    
    # Query the project
    db_project = db.query(Project).filter(Project.id == project_id).first()
    
    # Check if project exists
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if user has access to the project
    if db_project.creator_email == user_email:
        # User is the creator, always has access
        return db_project
    
    # Check if user is in the project's authorization group
    if is_user_in_group(user_email, db_project.authorization_group):
        return db_project
    
    # User doesn't have access
    raise HTTPException(status_code=403, detail="You don't have access to this project")

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, project: ProjectUpdate, request: Request, db: Session = Depends(get_postgres_db)):
    """Update a project (only creator can update)"""
    # Get user email from request state
    user_email = request.state.user_email
    
    # Query the project
    db_project = db.query(Project).filter(Project.id == project_id).first()
    
    # Check if project exists
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if user is the creator
    if db_project.creator_email != user_email:
        raise HTTPException(status_code=403, detail="Only the creator can update the project")
    
    # Update project fields if provided
    if project.name is not None:
        db_project.name = project.name
    if project.description is not None:
        db_project.description = project.description
    if project.authorization_group is not None:
        db_project.authorization_group = project.authorization_group
    
    # Update the updated_at timestamp
    db_project.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(db_project)
        return db_project
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error updating project"
        )

@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
def delete_project(project_id: int, request: Request, db: Session = Depends(get_postgres_db)):
    """Delete a project (only creator can delete)"""
    # Get user email from request state
    user_email = request.state.user_email
    
    # Query the project
    db_project = db.query(Project).filter(Project.id == project_id).first()
    
    # Check if project exists
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if user is the creator
    if db_project.creator_email != user_email:
        raise HTTPException(status_code=403, detail="Only the creator can delete the project")
    
    try:
        # Delete the project
        db.delete(db_project)
        db.commit()
        return {"message": "Project deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting project: {str(e)}"
        )
