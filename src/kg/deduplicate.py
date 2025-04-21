import os
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from openai import OpenAI
from neo4j import GraphDatabase
# from dotenv import load_dotenv

# Load environment variables from .env file
# load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if not os.getenv("OPENAI_API_KEY"):
    logger.warning("OPENAI_API_KEY environment variable not set. OpenAI calls will fail.")

# Get model from environment
model = os.getenv("OPENAI_MODEL", "gpt-4")
logger.info(f"Using OpenAI model: {model}")

# Neo4j connection configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

# --- Pydantic Models ---
class DeduplicationRequest(BaseModel):
    """Request model for deduplication."""
    limit: int = Field(10, description="Number of most recent entities to check for duplicates")

class EntityInfo(BaseModel):
    """Basic information about an entity."""
    id: str = Field(..., description="ID of the entity")
    name: str = Field(..., description="Name of the entity")
    description: str = Field(..., description="Description of the entity")

class DuplicatePair(BaseModel):
    """Model for a pair of entities that might be duplicates."""
    entity1_id: str = Field(..., description="ID of the first entity")
    entity1_name: str = Field(..., description="Name of the first entity")
    entity2_id: str = Field(..., description="ID of the second entity")
    entity2_name: str = Field(..., description="Name of the second entity")
    confidence_score: float = Field(..., description="Confidence score from 0 to 10, where 0 means definitely not duplicates and 10 means definitely duplicates")
    reasoning: str = Field(..., description="Explanation of why these entities are considered potential duplicates")

class BatchDeduplicationResult(BaseModel):
    """Model for OpenAI's batch deduplication response."""
    duplicate_pairs: List[DuplicatePair] = Field(..., description="List of potential duplicate entity pairs")

class DeduplicationResponse(BaseModel):
    """Response model for deduplication results."""
    total_entities_checked: int = Field(..., description="Total number of entities checked")
    potential_duplicates_found: int = Field(..., description="Number of potential duplicate pairs found")
    duplicates: List[DuplicatePair] = Field([], description="List of potential duplicate pairs")

async def find_potential_duplicates(limit: int, project_id: int) -> DeduplicationResponse: # Added project_id
    """
    Find potential duplicates in the Neo4j database for a specific project
    by sending a batch of entities to OpenAI.
    
    Args:
        limit: Number of most recent entities to check within the project
        project_id: The ID of the project to check within
        
    Returns:
        DeduplicationResponse with potential duplicates
    """
    logger.info(f"Checking up to {limit} entities for duplicates in batch mode...")
    
    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with driver.session() as session:
            # Get entities to check within the specified project
            entities = session.run(
                """
                MATCH (p:Person {project_id: $project_id})
                RETURN ID(p) as id, p.name as name, p.description as description
                ORDER BY ID(p) DESC
                LIMIT $limit
                """,
                project_id=project_id, # Pass project_id
                limit=limit
            ).data()
            
            # If we have fewer than 2 entities, there can't be any duplicates
            if len(entities) < 2:
                return DeduplicationResponse(
                    total_entities_checked=len(entities),
                    potential_duplicates_found=0,
                    duplicates=[]
                )
            
            # Format entities for the prompt
            entity_list = []
            for entity in entities:
                entity_list.append({
                    "id": str(entity['id']),
                    "name": entity['name'] or "Unknown",
                    "description": entity['description'] or ""
                })
            
            # Check for duplicates using OpenAI
            result = await batch_check_duplicates(entity_list)

            # Filter out any pairs where entity1_id == entity2_id (no self-pairs)
            filtered_pairs = [
                pair for pair in result.duplicate_pairs
                if str(pair.entity1_id) != str(pair.entity2_id)
            ]
            
            # Create response
            return DeduplicationResponse(
                total_entities_checked=len(entities),
                potential_duplicates_found=len(filtered_pairs),
                duplicates=filtered_pairs
            )
    
    finally:
        driver.close()

async def batch_check_duplicates(entities: List[Dict[str, str]]) -> BatchDeduplicationResult:
    """
    Use OpenAI to identify potential duplicate entities from a batch.
    
    Args:
        entities: List of entity dictionaries with id, name, and description
        
    Returns:
        BatchDeduplicationResult with potential duplicate pairs
    """
    logger.info(f"Checking batch of {len(entities)} entities for duplicates...")
    
    try:
        # Create the prompt for OpenAI
        entities_json = "\n".join([
            f"{i+1}. ID: {entity['id']}, Name: {entity['name']}, Description: {entity['description']}"
            for i, entity in enumerate(entities)
        ])
        
        prompt = f"""Analyze this list of entities and identify any potential duplicates:

{entities_json}

For each pair of entities that might be duplicates, provide:
1. The IDs of both entities
2. A confidence score from 0-10 (0 = definitely not duplicates, 10 = definitely duplicates)
3. A brief explanation of why you think they might be duplicates

Only include pairs with a confidence score of 5 or higher. If no potential duplicates are found, return an empty list.
"""
        # Log the prompt and entities for debugging
        logger.info(f"Checking batch of {len(entities)} entities for duplicates")
        logger.debug(f"Entities being checked: {entities}")
        
        # Make the API call with structured output using Pydantic model
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert at entity resolution and deduplication."},
                {"role": "user", "content": prompt}
            ],
            response_format=BatchDeduplicationResult,
            temperature=0.1
        )
        
        result = completion.choices[0].message.parsed
        
        # Log the result for debugging
        logger.info(f"Found {len(result.duplicate_pairs)} potential duplicate pairs")
        if result.duplicate_pairs:
            for pair in result.duplicate_pairs:
                logger.info(f"Potential duplicate: {pair.entity1_name} (ID: {pair.entity1_id}) and {pair.entity2_name} (ID: {pair.entity2_id}) with confidence {pair.confidence_score}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error checking for duplicates in batch: {e}", exc_info=True)
        # Return an empty result in case of error
        return BatchDeduplicationResult(duplicate_pairs=[])

async def merge_duplicate_entities(
    entity_id: str, 
    duplicate_id: str, 
    user_email: str = None, 
    current_time: str = None, 
    project_id: int = None # Added project_id
) -> Dict[str, Any]:
    """
    Merge two duplicate entities in the Neo4j database within a specific project.
    
    Args:
        entity_id: ID of the entity to keep
        duplicate_id: ID of the duplicate entity to merge
        user_email: Email of the user performing the merge
        current_time: Timestamp of the merge operation
        project_id: The ID of the project where the merge should occur
        
    Returns:
        Dictionary with the result of the merge operation
    """
    logger.info(f"Merging entity {duplicate_id} into {entity_id}...")

    # Prevent merging an entity with itself
    if str(entity_id) == str(duplicate_id):
        raise ValueError("Cannot merge an entity with itself.")

    # If current_time is not provided, generate it
    if current_time is None:
        from datetime import datetime
        current_time = datetime.utcnow().isoformat()
    
    if project_id is None:
        raise ValueError("project_id is required for merging entities")
        
    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with driver.session() as session:
            # Verify both entities exist in the project before proceeding
            check = session.run(
                """
                MATCH (keep:Person {project_id: $project_id}) WHERE ID(keep) = $entity_id
                MATCH (dup:Person {project_id: $project_id}) WHERE ID(dup) = $duplicate_id
                RETURN keep, dup
                """,
                project_id=project_id,
                entity_id=int(entity_id),
                duplicate_id=int(duplicate_id)
            ).single()
            
            if not check or not check["keep"] or not check["dup"]:
                 raise ValueError(f"One or both entities ({entity_id}, {duplicate_id}) not found in project {project_id}")

            # 1. Get all relationships of the duplicate entity within the project
            relationships = session.run(
                """
                MATCH (dup:Person {project_id: $project_id})-[r {project_id: $project_id}]->(other:Person {project_id: $project_id}) 
                WHERE ID(dup) = $duplicate_id
                RETURN ID(other) as target_id, type(r) as rel_type, 'outgoing' as direction
                UNION
                MATCH (other:Person {project_id: $project_id})-[r {project_id: $project_id}]->(dup:Person {project_id: $project_id}) 
                WHERE ID(dup) = $duplicate_id
                RETURN ID(other) as target_id, type(r) as rel_type, 'incoming' as direction
                """,
                project_id=project_id,
                duplicate_id=int(duplicate_id)
            ).data()
            
            # 2. Create equivalent relationships for the entity to keep within the project
            for rel in relationships:
                if rel['direction'] == 'outgoing':
                    # Create outgoing relationship with project_id and user tracking
                    session.run(
                        f"""
                        MATCH (keep:Person {{project_id: $project_id}}) WHERE ID(keep) = $entity_id
                        MATCH (other:Person {{project_id: $project_id}}) WHERE ID(other) = $target_id
                        MERGE (keep)-[r:{rel['rel_type']}]->(other)
                        ON CREATE SET r.project_id = $project_id, 
                                      r.created_by = $user_email,
                                      r.created_at = $current_time,
                                      r.updated_by = $user_email,
                                      r.updated_at = $current_time
                        """,
                        project_id=project_id,
                        entity_id=int(entity_id),
                        target_id=rel['target_id'],
                        user_email=user_email,
                        current_time=current_time
                    )
                else:
                    # Create incoming relationship with project_id and user tracking
                    session.run(
                        f"""
                        MATCH (keep:Person {{project_id: $project_id}}) WHERE ID(keep) = $entity_id
                        MATCH (other:Person {{project_id: $project_id}}) WHERE ID(other) = $target_id
                        MERGE (other)-[r:{rel['rel_type']}]->(keep)
                        ON CREATE SET r.project_id = $project_id,
                                      r.created_by = $user_email,
                                      r.created_at = $current_time,
                                      r.updated_by = $user_email,
                                      r.updated_at = $current_time
                        """,
                        project_id=project_id,
                        entity_id=int(entity_id),
                        target_id=rel['target_id'],
                        user_email=user_email,
                        current_time=current_time
                    )
            
            # 3. Delete the duplicate entity (which must be in the project)
            session.run(
                """
                MATCH (dup:Person {project_id: $project_id}) WHERE ID(dup) = $duplicate_id
                DETACH DELETE dup
                """,
                project_id=project_id,
                duplicate_id=int(duplicate_id)
            )
            
            return {
                "message": f"Successfully merged entity {duplicate_id} into {entity_id}",
                "entity_id": entity_id,
                "merged_id": duplicate_id,
                "relationships_transferred": len(relationships)
            }
    
    finally:
        driver.close()
