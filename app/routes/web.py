from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import List
import logging
from src.kg.deduplicate import merge_duplicate_entities
from app.utils.auth import check_user_authorization_groups
from app.utils.project_auth import verify_project_access
from app.postgres_db import get_postgres_db

router = APIRouter()

# Templates
templates = Jinja2Templates(directory="templates")

# Dependency to get the selected project from the session
async def get_selected_project(request: Request):
    """Get the selected project from the session"""
    project_id = request.session.get("selected_project_id")
    project_name = request.session.get("selected_project_name")
    
    return {
        "project_id": project_id,
        "project_name": project_name
    }

# Dependency to require a selected project with access verification
async def require_selected_project(request: Request, db = Depends(get_postgres_db)):
    """
    Requires a selected project for the route by verifying access using 
    the verify_project_access dependency. It handles missing project ID (400)
    or lack of access (403) by raising appropriate HTTPExceptions.
    If access is verified, returns the project details.
    """
    # verify_project_access handles checking query param/session and user access
    try:
        project_details = await verify_project_access(request=request, db=db)
        # Return the verified project details
        return project_details 
    except HTTPException as e:
        # If access denied (403), clear session and redirect
        if e.status_code == 403:
            # Clear the project from the session and redirect
            if "selected_project_id" in request.session:
                del request.session["selected_project_id"]
            if "selected_project_name" in request.session:
                del request.session["selected_project_name"]
            return RedirectResponse(url="/?error=project_access_denied")
        raise e

@router.get("/", response_class=HTMLResponse)
async def project_management(request: Request):
    """Project management page"""
    # Get user email from request state
    user_email = request.state.user_email
    
    # Get user's authorization groups from the mock external service
    user_auth_groups = check_user_authorization_groups(user_email)
    
    # Get selected project from session (if any)
    project = await get_selected_project(request)
    
    # Check for error message
    error = request.query_params.get("error")
    error_message = None
    if error == "no_project_selected":
        error_message = "Please select a project to continue"
    elif error == "project_access_denied":
        error_message = "You no longer have access to the previously selected project. Please select another project."
    
    return templates.TemplateResponse("projects.html", {
        "request": request,
        "user_email": user_email,
        "user_auth_groups": user_auth_groups,
        "selected_project_id": project["project_id"],
        "selected_project_name": project["project_name"],
        "error_message": error_message
    })

@router.get("/people", response_class=HTMLResponse)
async def people_management(
    request: Request,
    project: dict = Depends(require_selected_project)
):
    """People management page (moved from root)"""
    return templates.TemplateResponse("people.html", {
        "request": request,
        "user_email": request.state.user_email,
        "selected_project_id": project["project_id"],
        "selected_project_name": project["project_name"]
    })

@router.get("/visualize", response_class=HTMLResponse)
async def visualize_graph(
    request: Request,
    project: dict = Depends(require_selected_project)
):
    return templates.TemplateResponse("visualize.html", {
        "request": request,
        "user_email": request.state.user_email,
        "selected_project_id": project["project_id"],
        "selected_project_name": project["project_name"]
    })

@router.get("/extract-kg", response_class=HTMLResponse)
async def extract_kg_page(
    request: Request,
    project: dict = Depends(require_selected_project)
):
    return templates.TemplateResponse("extract_kg.html", {
        "request": request,
        "user_email": request.state.user_email,
        "selected_project_id": project["project_id"],
        "selected_project_name": project["project_name"]
    })

@router.get("/deduplicate", response_class=HTMLResponse)
async def deduplicate_page(
    request: Request, 
    project: dict = Depends(require_selected_project),
    success: bool = False
):
    """
    Render the deduplication UI page.
    
    This endpoint renders the template with a loading spinner.
    The actual deduplication is performed client-side via JavaScript
    calling the /api/kg/deduplicate endpoint.
    """
    context = {
        "request": request,
        "user_email": request.state.user_email,
        "selected_project_id": project["project_id"],
        "selected_project_name": project["project_name"]
    }
    
    if success:
        context["success"] = True
        context["message"] = "Successfully merged duplicate entities."
    
    return templates.TemplateResponse("deduplicate.html", context)

@router.get("/viz2", response_class=HTMLResponse)
async def viz2_page(
    request: Request,
    project: dict = Depends(require_selected_project)
):
    """
    Render the new 2D knowledge graph visualization page (viz2).
    """
    return templates.TemplateResponse("viz2.html", {
        "request": request,
        "user_email": request.state.user_email,
        "selected_project_id": project["project_id"],
        "selected_project_name": project["project_name"]
    })

# Note: The /deduplicate/merge endpoint is no longer used
# Merges are now handled directly through the API endpoint /api/kg/merge
# and processed via JavaScript in the client
