from fastapi import APIRouter, HTTPException, Form, Request, Depends # Added Depends
from typing import Dict, Any
import logging
from datetime import datetime
from app.models.models import DeduplicationRequest, DeduplicationResponse
from src.kg.deduplicate import find_potential_duplicates, merge_duplicate_entities
from app.utils.project_auth import verify_project_access # Added import

router = APIRouter(prefix="/api/kg")

@router.post("/deduplicate", response_model=DeduplicationResponse)
async def deduplicate_entities(
    request: DeduplicationRequest,
    # Project details are injected by the dependency based on query param or session
    project_details: dict = Depends(verify_project_access) 
):
    """
    Find potential duplicate entities in the knowledge graph using batch processing.
    
    This endpoint sends a batch of N entities to the OpenAI API and uses AI
    to identify potential duplicate pairs among them.
    """
    try:
        # Find potential duplicates using batch processing, passing project_id
        project_id = project_details["project_id"] # Get project_id from dependency result
        result = await find_potential_duplicates(request.limit, project_id) # Pass project_id
        # Ensure the result matches the expected response model
        return {
            "duplicates": result.duplicates,
            "total_entities_checked": result.total_entities_checked,
            "potential_duplicates_found": result.potential_duplicates_found
        }
    
    except Exception as e:
        logging.error(f"Error during deduplication: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to deduplicate entities: {str(e)}")

@router.post("/merge", response_model=Dict[str, Any])
async def merge_entities(
    entity_id: str = Form(...), 
    duplicate_id: str = Form(...), 
    request: Request = None,
    # Project details are injected by the dependency based on query param or session
    project_details: dict = Depends(verify_project_access) 
):
    """
    Merge two duplicate entities in the knowledge graph.
    
    This endpoint merges the duplicate entity into the main entity,
    transferring all relationships and then deleting the duplicate.
    """
    try:
        # Convert entity IDs to int
        try:
            entity_id_int = int(entity_id)
            duplicate_id_int = int(duplicate_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Entity IDs must be integers.")

        # Prevent merging an entity with itself
        if entity_id_int == duplicate_id_int:
            raise HTTPException(status_code=400, detail="Cannot merge an entity with itself.")

        # Get user email from request state if available
        user_email = request.state.user_email if request else None
        # Get project ID from dependency result
        project_id = project_details["project_id"] 
        # Get current timestamp
        current_time = datetime.utcnow().isoformat()
        
        # Merge the duplicate entities with user tracking and project_id
        result = await merge_duplicate_entities(entity_id_int, duplicate_id_int, user_email, current_time, project_id)
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error merging entities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to merge entities: {str(e)}")
