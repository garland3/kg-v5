from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List
import logging
from datetime import datetime
from app.database import Neo4jDriver, get_db
from app.models.models import Person, PersonCreate, PersonUpdate, RelationshipCreate
from app.utils.project_auth import verify_project_access # Added import

router = APIRouter(prefix="/api")

# Create a person
@router.post("/people/", response_model=Person)
def create_person(
    person: PersonCreate, 
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
    
    with db.get_session() as session:
        # Create person node in Neo4j with project_id and user tracking
        result = session.run(
            """
            CREATE (p:Person {
                name: $name, 
                description: $description, 
                age: $age, 
                email: $email,
                project_id: $project_id, // Added project_id
                created_by: $created_by, 
                created_at: $created_at,
                updated_by: $updated_by,
                updated_at: $updated_at
            })
            RETURN p, ID(p) as id
            """,
            name=person.name,
            description=person.description,
            age=person.age,
            email=person.email,
            project_id=project_id, # Pass project_id
            created_by=user_email,
            created_at=current_time,
            updated_by=user_email,
            updated_at=current_time
        )
        
        data = result.single()
        if not data:
            raise HTTPException(status_code=500, detail="Failed to create person")
        
        # Get the created node
        node = data["p"]
        node_id = str(data["id"])
        
        # Return the created person with ID and tracking info
        return {
            "id": node_id,
            "name": node.get("name", "Unknown"),
            "description": node.get("description", ""),
            "age": node.get("age", None),
            "email": node.get("email", None),
            "created_by": node.get("created_by", None),
            "created_at": node.get("created_at", None),
            "updated_by": node.get("updated_by", None),
            "updated_at": node.get("updated_at", None)
        }

# Get all people with pagination for the current project
@router.get("/people/", response_model=dict)
def read_people(
    page: int = 1, 
    limit: int = 10, 
    db: Neo4jDriver = Depends(get_db),
    # Project details are injected by the dependency based on query param or session
    project_details: dict = Depends(verify_project_access) 
):
    project_id = project_details["project_id"] # Get project_id from dependency result
    with db.get_session() as session:
        # Get total count for the project
        count_result = session.run(
            "MATCH (p:Person {project_id: $project_id}) RETURN count(p) as total",
            project_id=project_id
        )
        total = count_result.single()["total"]
        
        # Calculate skip value for pagination
        skip = (page - 1) * limit
        
        # Get paginated results for the project
        result = session.run(
            "MATCH (p:Person {project_id: $project_id}) RETURN p, ID(p) as id ORDER BY p.name SKIP $skip LIMIT $limit",
            project_id=project_id,
            skip=skip,
            limit=limit
        )
        
        people = []
        for record in result:
            node = record["p"]
            node_id = str(record["id"])
            
            # Use .get() with default values to handle missing properties
            people.append({
                "id": node_id,
                "name": node.get("name", "Unknown"),  # Default to "Unknown" if name is missing
                "description": node.get("description", ""),  # Default to empty string if description is missing
                "age": node.get("age", None),
                "email": node.get("email", None),
                "created_by": node.get("created_by", None),
                "created_at": node.get("created_at", None),
                "updated_by": node.get("updated_by", None),
                "updated_at": node.get("updated_at", None)
            })
        
        # Return paginated response
        return {
            "items": people,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit  # Ceiling division to get total pages
        }

# Get all people without pagination for the current project (for visualization)
@router.get("/people/all/", response_model=List[Person])
def read_all_people(
    db: Neo4jDriver = Depends(get_db),
    # Project details are injected by the dependency based on query param or session
    project_details: dict = Depends(verify_project_access) 
):
    project_id = project_details["project_id"] # Get project_id from dependency result
    with db.get_session() as session:
        result = session.run(
            "MATCH (p:Person {project_id: $project_id}) RETURN p, ID(p) as id ORDER BY p.name",
            project_id=project_id
        )
        
        people = []
        for record in result:
            node = record["p"]
            node_id = str(record["id"])
            
            # Use .get() with default values to handle missing properties
            people.append({
                "id": node_id,
                "name": node.get("name", "Unknown"),  # Default to "Unknown" if name is missing
                "description": node.get("description", ""),  # Default to empty string if description is missing
                "age": node.get("age", None),
                "email": node.get("email", None),
                "created_by": node.get("created_by", None),
                "created_at": node.get("created_at", None),
                "updated_by": node.get("updated_by", None),
                "updated_at": node.get("updated_at", None)
            })
        
        return people

# Get a specific person by ID within the current project
@router.get("/people/{person_id}", response_model=Person)
def read_person(
    person_id: str, 
    db: Neo4jDriver = Depends(get_db),
    # Project details are injected by the dependency based on query param or session
    project_details: dict = Depends(verify_project_access) 
):
    project_id = project_details["project_id"] # Get project_id from dependency result
    try:
        person_node_id = int(person_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid person ID format")
        
    with db.get_session() as session:
        result = session.run(
            "MATCH (p:Person {project_id: $project_id}) WHERE ID(p) = $id RETURN p, ID(p) as id",
            project_id=project_id,
            id=person_node_id
        )
        
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="Person not found")
        
        node = record["p"]
        node_id = str(record["id"])
        
        return {
            "id": node_id,
            "name": node.get("name", "Unknown"),  # Default to "Unknown" if name is missing
            "description": node.get("description", ""),  # Default to empty string if description is missing
            "age": node.get("age", None),
            "email": node.get("email", None),
            "created_by": node.get("created_by", None),
            "created_at": node.get("created_at", None),
            "updated_by": node.get("updated_by", None),
            "updated_at": node.get("updated_at", None)
        }

# Update a person within the current project
@router.put("/people/{person_id}", response_model=Person)
def update_person(
    person_id: str, 
    person: PersonUpdate, 
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
        person_node_id = int(person_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid person ID format")
        
    # Build dynamic update query
    set_clauses = []
    params = {"id": person_node_id, "project_id": project_id, "updated_by": user_email, "updated_at": current_time}
    
    if person.name is not None:
        set_clauses.append("p.name = $name")
        params["name"] = person.name
    
    if person.description is not None:
        set_clauses.append("p.description = $description")
        params["description"] = person.description
    
    if person.age is not None:
        set_clauses.append("p.age = $age")
        params["age"] = person.age
    
    if person.email is not None:
        set_clauses.append("p.email = $email")
        params["email"] = person.email
    
    # Always update the updated_by and updated_at fields
    set_clauses.append("p.updated_by = $updated_by")
    set_clauses.append("p.updated_at = $updated_at")
    
    if len(set_clauses) <= 2:  # Only updated_by and updated_at
        raise HTTPException(status_code=400, detail="No fields to update")
    
    set_query = "SET " + ", ".join(set_clauses)
    
    with db.get_session() as session:
        # Update person in Neo4j, ensuring it's within the project
        query = f"""
        MATCH (p:Person {{project_id: $project_id}})
        WHERE ID(p) = $id
        {set_query}
        RETURN p, ID(p) as id
        """
        
        result = session.run(query, **params)
        record = result.single()
        
        if not record:
            raise HTTPException(status_code=404, detail="Person not found")
        
        node = record["p"]
        node_id = str(record["id"])
        
        return {
            "id": node_id,
            "name": node.get("name", "Unknown"),  # Default to "Unknown" if name is missing
            "description": node.get("description", ""),  # Default to empty string if description is missing
            "age": node.get("age", None),
            "email": node.get("email", None),
            "created_by": node.get("created_by", None),
            "created_at": node.get("created_at", None),
            "updated_by": node.get("updated_by", None),
            "updated_at": node.get("updated_at", None)
        }

# Delete a person within the current project
@router.delete("/people/{person_id}")
def delete_person(
    person_id: str, 
    db: Neo4jDriver = Depends(get_db),
    # Project details are injected by the dependency based on query param or session
    project_details: dict = Depends(verify_project_access) 
):
    project_id = project_details["project_id"] # Get project_id from dependency result
    try:
        person_node_id = int(person_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid person ID format")
        
    with db.get_session() as session:
        # First check if person exists within the project
        check = session.run(
            "MATCH (p:Person {project_id: $project_id}) WHERE ID(p) = $id RETURN p",
            project_id=project_id,
            id=person_node_id
        )
        
        if not check.single():
            raise HTTPException(status_code=404, detail="Person not found in this project")
        
        # Delete person from Neo4j within the project
        result = session.run(
            "MATCH (p:Person {project_id: $project_id}) WHERE ID(p) = $id DETACH DELETE p",
            project_id=project_id,
            id=person_node_id
        )
        
        return {"message": "Person deleted successfully"}

# Create a relationship between two people within the current project
@router.post("/relationships/")
def create_relationship(
    relationship: RelationshipCreate, 
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
        person1_node_id = int(relationship.person1_id)
        person2_node_id = int(relationship.person2_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid person ID format")
        
    with db.get_session() as session:
        # Check if both people exist within the project
        check = session.run(
            """
            MATCH (p1:Person {project_id: $project_id}) WHERE ID(p1) = $id1
            MATCH (p2:Person {project_id: $project_id}) WHERE ID(p2) = $id2
            RETURN p1, p2
            """,
            project_id=project_id,
            id1=person1_node_id,
            id2=person2_node_id
        )
        
        record = check.single()
        if not record or not record["p1"] or not record["p2"]:
            raise HTTPException(status_code=404, detail="One or both people not found in this project")
        
        # Process relationship type to make it Neo4j compatible
        # Replace spaces with underscores for Neo4j compatibility
        rel_type = relationship.relationship_type.replace(' ', '_')
        logging.info(f"Creating relationship with type: {rel_type}")
        
        # Create relationship with project_id - use dynamic query with f-string
        query = f"""
            MATCH (p1:Person {{project_id: $project_id}}) WHERE ID(p1) = $id1
            MATCH (p2:Person {{project_id: $project_id}}) WHERE ID(p2) = $id2
            CREATE (p1)-[r:{rel_type} {{
                project_id: $project_id, // Added project_id
                created_by: $created_by,
                created_at: $created_at,
                updated_by: $updated_by,
                updated_at: $updated_at
            }}]->(p2)
            RETURN p1, p2, type(r) as relationship_type
            """
        
        logging.info(f"Executing query: {query}")
        
        result = session.run(
            query,
            id1=person1_node_id,
            id2=person2_node_id,
            project_id=project_id, # Pass project_id
            created_by=user_email,
            created_at=current_time,
            updated_by=user_email,
            updated_at=current_time
        )
        
        record = result.single()
        if not record:
            raise HTTPException(status_code=500, detail="Failed to create relationship")
        
        return {"message": f"Relationship '{relationship.relationship_type}' created successfully"}

# Get all relationships for a person within the current project
@router.get("/people/{person_id}/relationships")
def read_relationships(
    person_id: str, 
    db: Neo4jDriver = Depends(get_db),
    # Project details are injected by the dependency based on query param or session
    project_details: dict = Depends(verify_project_access) 
):
    project_id = project_details["project_id"] # Get project_id from dependency result
    try:
        person_node_id = int(person_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid person ID format")
        
    with db.get_session() as session:
        # First check if the person exists in the project
        check = session.run(
            "MATCH (p:Person {project_id: $project_id}) WHERE ID(p) = $id RETURN p",
            project_id=project_id,
            id=person_node_id
        )
        if not check.single():
             raise HTTPException(status_code=404, detail="Person not found in this project")
             
        # Get relationships within the project
        result = session.run(
            """
            MATCH (p1:Person {project_id: $project_id})-[r {project_id: $project_id}]->(p2:Person {project_id: $project_id}) 
            WHERE ID(p1) = $id
            RETURN p1, p2, r, type(r) as relationship_type, ID(p2) as related_id, 'outgoing' as direction
            UNION
            MATCH (p1:Person {project_id: $project_id})<-[r {project_id: $project_id}]-(p2:Person {project_id: $project_id}) 
            WHERE ID(p1) = $id
            RETURN p1, p2, r, type(r) as relationship_type, ID(p2) as related_id, 'incoming' as direction
            """,
            project_id=project_id,
            id=person_node_id
        )
        
        relationships = []
        for record in result:
            p2 = record["p2"]
            # Convert relationship_type back from Neo4j format (underscores) to display format (spaces)
            rel_type = record["relationship_type"].replace('_', ' ')
            
            # Get relationship properties
            rel = record["r"]
            
            relationships.append({
                "person_id": person_id,
                "related_person_id": str(record["related_id"]),
                "related_person_name": p2.get("name", "Unknown"),  # Default to "Unknown" if name is missing
                "relationship_type": rel_type,
                "direction": record["direction"],
                "created_by": rel.get("created_by", None),
                "created_at": rel.get("created_at", None),
                "updated_by": rel.get("updated_by", None),
                "updated_at": rel.get("updated_at", None)
            })
            
        return relationships

# Get all relationships in the current project with pagination
@router.get("/relationships/")
def read_all_relationships(
    page: int = 1, 
    limit: int = 10, 
    db: Neo4jDriver = Depends(get_db),
    # Project details are injected by the dependency based on query param or session
    project_details: dict = Depends(verify_project_access) 
):
    project_id = project_details["project_id"] # Get project_id from dependency result
    with db.get_session() as session:
        # Get total count for the project
        count_result = session.run(
            "MATCH (p1:Person {project_id: $project_id})-[r {project_id: $project_id}]->(p2:Person {project_id: $project_id}) RETURN count(r) as total",
            project_id=project_id
        )
        total = count_result.single()["total"]
        
        # Calculate skip value for pagination
        skip = (page - 1) * limit
        
        # Get paginated results with relationship properties for the project
        result = session.run(
            """
            MATCH (p1:Person {project_id: $project_id})-[r {project_id: $project_id}]->(p2:Person {project_id: $project_id})
            RETURN ID(p1) as source_id, p1.name as source_name, 
                   ID(p2) as target_id, p2.name as target_name, 
                   type(r) as relationship_type, r
            ORDER BY p1.name, p2.name
            SKIP $skip LIMIT $limit
            """,
            project_id=project_id,
            skip=skip,
            limit=limit
        )
        
        relationships = []
        for record in result:
            # Convert relationship_type back from Neo4j format (underscores) to display format (spaces)
            rel_type = record["relationship_type"].replace('_', ' ')
            
            # Get relationship properties
            rel = record["r"]
            
            relationships.append({
                "source_id": str(record["source_id"]),
                "source_name": record["source_name"] or "Unknown",
                "target_id": str(record["target_id"]),
                "target_name": record["target_name"] or "Unknown",
                "relationship_type": rel_type,
                "created_by": rel.get("created_by", None),
                "created_at": rel.get("created_at", None),
                "updated_by": rel.get("updated_by", None),
                "updated_at": rel.get("updated_at", None)
            })
        
        # Return paginated response
        return {
            "items": relationships,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit  # Ceiling division to get total pages
        }
