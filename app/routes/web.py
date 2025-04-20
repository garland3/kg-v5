from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from typing import List
import logging
from src.kg.deduplicate import merge_duplicate_entities

router = APIRouter()

# Templates
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user_email": request.state.user_email
    })

@router.get("/visualize", response_class=HTMLResponse)
async def visualize_graph(request: Request):
    return templates.TemplateResponse("visualize.html", {
        "request": request,
        "user_email": request.state.user_email
    })

@router.get("/extract-kg", response_class=HTMLResponse)
async def extract_kg_page(request: Request):
    return templates.TemplateResponse("extract_kg.html", {
        "request": request,
        "user_email": request.state.user_email
    })

@router.get("/deduplicate", response_class=HTMLResponse)
async def deduplicate_page(request: Request, success: bool = False):
    """
    Render the deduplication UI page.
    
    This endpoint renders the template with a loading spinner.
    The actual deduplication is performed client-side via JavaScript
    calling the /api/kg/deduplicate endpoint.
    """
    context = {
        "request": request,
        "user_email": request.state.user_email
    }
    
    if success:
        context["success"] = True
        context["message"] = "Successfully merged duplicate entities."
    
    return templates.TemplateResponse("deduplicate.html", context)

# Note: The /deduplicate/merge endpoint is no longer used
# Merges are now handled directly through the API endpoint /api/kg/merge
# and processed via JavaScript in the client
