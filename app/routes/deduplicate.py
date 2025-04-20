from fastapi import APIRouter, HTTPException, Form, Request
from typing import Dict, Any
import logging
from datetime import datetime
from app.models.models import DeduplicationRequest, DeduplicationResponse
from src.kg.deduplicate import find_potential_duplicates, merge_duplicate_entities

router = APIRouter(prefix="/api/kg")

@router.post("/deduplicate", response_model=DeduplicationResponse)
async def deduplicate_entities(request: DeduplicationRequest):
    """
    Find potential duplicate entities in the knowledge graph using batch processing.
    
    This endpoint sends a batch of N entities to the OpenAI API and uses AI
    to identify potential duplicate pairs among them.
    """
    try:
        # Find potential duplicates using batch processing
        result = await find_potential_duplicates(request.limit)
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
async def merge_entities(entity_id: str = Form(...), duplicate_id: str = Form(...), request: Request = None):
    """
    Merge two duplicate entities in the knowledge graph.
    
    This endpoint merges the duplicate entity into the main entity,
    transferring all relationships and then deleting the duplicate.
    """
    try:
        # Get user email from request state if available
        user_email = request.state.user_email if request else None
        # Get current timestamp
        current_time = datetime.utcnow().isoformat()
        
        # Merge the duplicate entities with user tracking
        result = await merge_duplicate_entities(entity_id, duplicate_id, user_email, current_time)
        return result
    
    except Exception as e:
        logging.error(f"Error merging entities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to merge entities: {str(e)}")
