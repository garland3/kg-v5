from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.postgres_db import get_postgres_db
from app.models.postgres_models import Project
from app.utils.project_auth import check_project_access

router = APIRouter(
    prefix="/api/session",
    tags=["session"],
    responses={404: {"description": "Not found"}},
)

# Pydantic models for request/response
class ProjectSelection(BaseModel):
    project_id: int
    project_name: str

class SessionResponse(BaseModel):
    message: str
    project_id: Optional[int] = None
    project_name: Optional[str] = None

@router.post("/select-project", response_model=SessionResponse)
async def select_project(project_data: ProjectSelection, request: Request, db: Session = Depends(get_postgres_db)):
    """Select a project and save it to the session"""
    # Get user email from request state
    user_email = request.state.user_email
    
    # Verify that the project exists and user has access to it
    if not check_project_access(project_data.project_id, user_email, db):
        raise HTTPException(status_code=403, detail="You don't have access to this project")
    
    # Get project details
    db_project = db.query(Project).filter(Project.id == project_data.project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Save project to session
    request.session["selected_project_id"] = project_data.project_id
    request.session["selected_project_name"] = project_data.project_name
    
    return {
        "message": f"Project '{project_data.project_name}' selected successfully",
        "project_id": project_data.project_id,
        "project_name": project_data.project_name
    }

@router.get("/current-project", response_model=SessionResponse)
async def get_current_project(request: Request):
    """Get the currently selected project from the session"""
    project_id = request.session.get("selected_project_id")
    project_name = request.session.get("selected_project_name")
    
    if not project_id:
        return {
            "message": "No project selected",
            "project_id": None,
            "project_name": None
        }
    
    return {
        "message": f"Current project: {project_name}",
        "project_id": project_id,
        "project_name": project_name
    }

@router.post("/clear-project", response_model=SessionResponse)
async def clear_project(request: Request):
    """Clear the selected project from the session"""
    if "selected_project_id" in request.session:
        del request.session["selected_project_id"]
    
    if "selected_project_name" in request.session:
        del request.session["selected_project_name"]
    
    return {
        "message": "Project selection cleared",
        "project_id": None,
        "project_name": None
    }
