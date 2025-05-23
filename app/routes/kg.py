from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, Any
import logging
from datetime import datetime
from app.database import Neo4jDriver, get_db
from app.models.models import TextInput
from src.kg.kg import extract_knowledge_graph_from_text, read_file_content
from app.utils.project_auth import verify_project_access # Added import

import os
from openai import OpenAI

router = APIRouter(prefix="/api/kg")

# Extract knowledge graph from text
@router.post("/extract", response_model=Dict[str, Any])
async def extract_kg_from_text(
    text_input: TextInput,
    # Project details are injected by the dependency based on query param or session
    project_details: dict = Depends(verify_project_access) 
):
    try:
        # Extract knowledge graph from text, passing project_id
        project_id = project_details["project_id"] # Get project_id from dependency result
        kg = await extract_knowledge_graph_from_text(text_input.text, project_id) # Pass project_id
        
        # Convert entities and relationships to dictionaries for JSON response
        entities = []
        relationships = []
        
        for entity in kg.entities:
            entities.append({
                "entity_id": entity.entity_id,
                "label": entity.label,
                "type": entity.type,
                "description": entity.description
            })
        
        for rel in kg.relationships:
            relationships.append({
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "label": rel.label
            })
        
        return {
            "message": "Knowledge graph extracted successfully",
            "entities": entities,
            "relationships": relationships
        }
    
    except Exception as e:
        logging.error(f"Error extracting knowledge graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to extract knowledge graph: {str(e)}")

# Upload file and extract knowledge graph
@router.post("/upload", response_model=Dict[str, Any])
async def upload_file_extract_kg(
    file: UploadFile = File(...),
    # Project details are injected by the dependency based on query param or session
    project_details: dict = Depends(verify_project_access) 
):
    try:
        # Read file content
        text = await read_file_content(file)
        
        # Create TextInput object
        text_input = TextInput(text=text)
        
        # Use the extract_kg_from_text function directly to process the text, passing project_id
        project_id = project_details["project_id"] # Get project_id from dependency result
        kg = await extract_knowledge_graph_from_text(text_input.text, project_id) # Pass project_id
        
        # Convert entities and relationships to dictionaries for JSON response
        entities = []
        relationships = []
        
        for entity in kg.entities:
            entities.append({
                "entity_id": entity.entity_id,
                "label": entity.label,
                "type": entity.type,
                "description": entity.description
            })
        
        for rel in kg.relationships:
            relationships.append({
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "label": rel.label
            })
        
        return {
            "message": "Knowledge graph extracted successfully",
            "entities": entities,
            "relationships": relationships
        }
    
    except Exception as e:
        logging.error(f"Error processing uploaded file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process uploaded file: {str(e)}")

# Export the current knowledge graph as a downloadable JSON file
@router.get("/export")
async def export_kg(
    db: Neo4jDriver = Depends(get_db),
    project_details: dict = Depends(verify_project_access)
):
    """
    Export the current knowledge graph (nodes and edges) for the selected project as a downloadable JSON file.
    """
    import io
    import json

    project_id = project_details["project_id"]

    # Query all people (nodes)
    with db.get_session() as session:
        people_result = session.run(
            "MATCH (p:Person {project_id: $project_id}) RETURN p, ID(p) as id ORDER BY p.name",
            project_id=project_id
        )
        nodes = []
        node_ids = set()
        for record in people_result:
            node = record["p"]
            node_id = str(record["id"])
            node_ids.add(node_id)
            nodes.append({
                "id": node_id,
                "name": node.get("name", "Unknown"),
                "description": node.get("description", ""),
                "age": node.get("age", None),
                "email": node.get("email", None),
                "created_by": node.get("created_by", None),
                "created_at": node.get("created_at", None),
                "updated_by": node.get("updated_by", None),
                "updated_at": node.get("updated_at", None)
            })

        # Query all relationships (edges) between people in this project
        rel_result = session.run(
            """
            MATCH (p1:Person {project_id: $project_id})-[r {project_id: $project_id}]->(p2:Person {project_id: $project_id})
            RETURN ID(p1) as source_id, ID(p2) as target_id, type(r) as relationship_type, r
            """,
            project_id=project_id
        )
        edges = []
        for record in rel_result:
            # Only include edges where both source and target are in the current node set
            source_id = str(record["source_id"])
            target_id = str(record["target_id"])
            if source_id in node_ids and target_id in node_ids:
                rel_type = record["relationship_type"].replace('_', ' ')
                rel = record["r"]
                edges.append({
                    "source_id": source_id,
                    "target_id": target_id,
                    "relationship_type": rel_type,
                    "created_by": rel.get("created_by", None),
                    "created_at": rel.get("created_at", None),
                    "updated_by": rel.get("updated_by", None),
                    "updated_at": rel.get("updated_at", None)
                })

    # Prepare JSON data
    export_data = {
        "nodes": nodes,
        "edges": edges
    }
    json_bytes = json.dumps(export_data, indent=2).encode("utf-8")
    file_like = io.BytesIO(json_bytes)

    # Return as downloadable file
    return StreamingResponse(
        file_like,
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=knowledge_graph_export.json"
        }
    )

# Store knowledge graph after approval
@router.post("/store", response_model=Dict[str, Any])
async def store_kg(
    kg_data: Dict[str, Any], 
    request: Request, 
    db: Neo4jDriver = Depends(get_db),
    # Project details are injected by the dependency based on query param or session
    project_details: dict = Depends(verify_project_access) 
):
    # Get user email from request state
    user_email = request.state.user_email
    # Get project ID from dependency result
    project_id = project_details["project_id"] 
    # Get current timestamp
    current_time = datetime.utcnow().isoformat()
    try:
        # Extract entities and relationships from the request
        entities = kg_data.get("entities", [])
        relationships = kg_data.get("relationships", [])
        
        stored_entities = []
        stored_relationships = []
        
        with db.get_session() as session:
            # Get the count of existing Person nodes *within the project* to use as an offset
            count_result = session.run(
                "MATCH (p:Person {project_id: $project_id}) RETURN COUNT(p) as count",
                project_id=project_id
            )
            count_record = count_result.single()
            offset = count_record["count"] if count_record else 0
            
            # Create a mapping between original entity IDs and new entity IDs
            id_mapping = {}
            
            # Store entities with new unique entity IDs
            openai_api_key = os.getenv("OPENAI_API_KEY")
            embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
            client = OpenAI(api_key=openai_api_key)
            for i, entity in enumerate(entities):
                # Create a new unique entity ID by adding the offset
                original_entity_id = entity["entity_id"]
                new_entity_id = str(int(offset) + i + 1)  # +1 to avoid starting at 0

                # Store the mapping
                id_mapping[original_entity_id] = new_entity_id

                # Generate embedding for the entity (name + description)
                name = entity["label"]
                description = entity["description"]
                text = f"{name or ''} - {description or ''}"
                embedding = None
                try:
                    response = client.embeddings.create(
                        input=text,
                        model=embedding_model
                    )
                    embedding = response.data[0].embedding
                except Exception as e:
                    logging.error(f"Error generating embedding for entity '{name}': {e}")

                # Create entity in Neo4j with the new entity ID, project_id, user tracking, and embedding
                result = session.run(
                    """
                    CREATE (p:Person {
                        entity_id: $entity_id,
                        original_entity_id: $original_entity_id,
                        name: $name,
                        description: $description,
                        project_id: $project_id,
                        created_by: $created_by,
                        created_at: $created_at,
                        updated_by: $updated_by,
                        updated_at: $updated_at,
                        embedding: $embedding
                    })
                    RETURN p, ID(p) as id
                    """,
                    entity_id=new_entity_id,
                    original_entity_id=original_entity_id,
                    name=name,
                    description=description,
                    project_id=project_id,
                    created_by=user_email,
                    created_at=current_time,
                    updated_by=user_email,
                    updated_at=current_time,
                    embedding=embedding
                )

                data = result.single()
                if data:
                    node = data["p"]
                    node_id = str(data["id"])
                    stored_entities.append({
                        "id": node_id,
                        "entity_id": node.get("entity_id", ""),
                        "original_entity_id": node.get("original_entity_id", ""),
                        "name": node.get("name", ""),
                        "description": node.get("description", "")
                    })
            
            # Store relationships using the new entity IDs
            for rel in relationships:
                # Get the new entity IDs from the mapping
                original_source_id = rel["source_id"]
                original_target_id = rel["target_id"]
                
                # Skip if either source or target is not in the mapping
                if original_source_id not in id_mapping or original_target_id not in id_mapping:
                    logging.warning(f"Skipping relationship: source {original_source_id} or target {original_target_id} not found in mapping")
                    continue
                
                new_source_id = id_mapping[original_source_id]
                new_target_id = id_mapping[original_target_id]
                
                # Find the Neo4j IDs for the source and target entities *within the project*
                source_result = session.run(
                    "MATCH (p:Person {entity_id: $entity_id, project_id: $project_id}) RETURN ID(p) as id",
                    entity_id=new_source_id,
                    project_id=project_id
                )
                source_record = source_result.single()
                
                target_result = session.run(
                    "MATCH (p:Person {entity_id: $entity_id, project_id: $project_id}) RETURN ID(p) as id",
                    entity_id=new_target_id,
                    project_id=project_id
                )
                target_record = target_result.single()
                
                if source_record and target_record:
                    source_id = source_record["id"]
                    target_id = target_record["id"]
                    
                    # Process relationship type to make it Neo4j compatible
                    rel_type = rel["label"].replace(' ', '_')
                    
                    # Create relationship with project_id and user tracking
                    query = f"""
                        MATCH (p1:Person) WHERE ID(p1) = $id1 AND p1.project_id = $project_id
                        MATCH (p2:Person) WHERE ID(p2) = $id2 AND p2.project_id = $project_id
                        CREATE (p1)-[r:{rel_type} {{
                            project_id: $project_id, // Added project_id
                            created_by: $created_by,
                            created_at: $created_at,
                            updated_by: $updated_by,
                            updated_at: $updated_at
                        }}]->(p2)
                        RETURN p1, p2, type(r) as relationship_type
                        """
                    
                    result = session.run(
                        query,
                        id1=source_id,
                        id2=target_id,
                        project_id=project_id, # Pass project_id
                        created_by=user_email,
                        created_at=current_time,
                        updated_by=user_email,
                        updated_at=current_time
                    )
                    
                    record = result.single()
                    if record:
                        stored_relationships.append({
                            "source_id": new_source_id,
                            "target_id": new_target_id,
                            "original_source_id": original_source_id,
                            "original_target_id": original_target_id,
                            "label": rel["label"]
                        })
        
        return {
            "message": "Knowledge graph stored successfully",
            "entities": stored_entities,
            "relationships": stored_relationships
        }
    
    except Exception as e:
        logging.error(f"Error storing knowledge graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to store knowledge graph: {str(e)}")
