from tqdm import tqdm
import os
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.utils.llm import get_llm_client
from openai import OpenAI
from neo4j import GraphDatabase
# from dotenv import load_dotenv

# Load environment variables from .env file
# load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
# (Replaced by get_llm_client for completions and embeddings)
client = get_llm_client()
if not os.getenv("OPENAI_API_KEY") and os.getenv("USE_OPENAI", "1").lower() in ("1", "true", "yes"):
    logger.warning("OPENAI_API_KEY environment variable not set. OpenAI calls will fail.")

# Get model from environment
model = os.getenv("OPENAI_MODEL", "gpt-4")
embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
logger.info(f"Using OpenAI model: {model}")
logger.info(f"Using OpenAI embedding model: {embedding_model}")

async def batch_generate_embeddings(project_id: Optional[int] = None, batch_size: int = 100):
    """
    Generate and store embeddings for all Person nodes (optionally by project) that do not have an embedding.
    """
    logger.info(f"Starting batch embedding generation for {'all projects' if project_id is None else f'project {project_id}'}")
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            while True:
                # Build query for batch of Person nodes without embedding
                query = """
                MATCH (p:Person)
                WHERE p.embedding IS NULL
                """
                if project_id is not None:
                    query += " AND p.project_id = $project_id"
                query += """
                RETURN ID(p) as id, p.name as name, p.description as description
                LIMIT $batch_size
                """
                params = {"batch_size": batch_size}
                if project_id is not None:
                    params["project_id"] = project_id
                entities = session.run(query, **params).data()
                if not entities:
                    break
                logger.info(f"Processing batch of {len(entities)} entities for embeddings")
                for entity in entities:
                    entity_id = entity["id"]
                    text = f"{entity['name'] or ''} - {entity['description'] or ''}"
                    try:
                        # Use the LLM abstraction for embeddings (supports OpenAI and vLLM)
                        embedding = client.embed_texts([text], model_name=embedding_model)[0]
                        session.run(
                            """
                            MATCH (p:Person) WHERE ID(p) = $entity_id
                            SET p.embedding = $embedding
                            """,
                            entity_id=entity_id,
                            embedding=embedding
                        )
                        logger.info(f"Set embedding for Person node {entity_id}")
                    except Exception as e:
                        logger.error(f"Error generating embedding for entity {entity_id}: {e}")
    finally:
        driver.close()
    logger.info("Batch embedding generation completed.")

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

class EntityNode(BaseModel):
    id: str
    name: str
    description: str
    embedding: Optional[list[float]] = None

class CandidatePair(BaseModel):
    entity1: EntityNode
    entity2: EntityNode
    vector_score: float

def get_recent_entities_with_embeddings(session, project_id: int, limit: int) -> list[EntityNode]:
    records = session.run(
        """
        MATCH (p:Person {project_id: $project_id})
        WHERE p.embedding IS NOT NULL
        RETURN ID(p) as id, p.name as name, p.description as description, p.embedding as embedding
        ORDER BY ID(p) DESC
        LIMIT $limit
        """,
        project_id=project_id,
        limit=limit
    ).data()
    return [
        EntityNode(
            id=str(r["id"]),
            name=r["name"] or "Unknown",
            description=r["description"] or "",
            embedding=r["embedding"]
        )
        for r in records
    ]

def get_vector_candidate_pairs(session, entities: list[EntityNode], project_id: int, similarity_threshold: float) -> list[CandidatePair]:
    processed_pairs = set()
    candidate_pairs = []
    for entity in entities:
        if not entity.embedding:
            continue
        similar_entities = session.run(
            """
            CALL db.index.vector.queryNodes('person_embeddings', 41, $embedding)
            YIELD node, score
            WHERE ID(node) <> $entity_id
              AND node.project_id = $project_id
              AND score > $threshold
            RETURN ID(node) as id, node.name as name, node.description as description, score
            ORDER BY score DESC
            LIMIT 40
            """,
            entity_id=int(entity.id),
            project_id=project_id,
            embedding=entity.embedding,
            threshold=similarity_threshold
        ).data()
        for similar in similar_entities:
            similar_id = str(similar["id"])
            pair_key = tuple(sorted([entity.id, similar_id]))
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)
            candidate_pairs.append(CandidatePair(
                entity1=entity,
                entity2=EntityNode(
                    id=similar_id,
                    name=similar["name"] or "Unknown",
                    description=similar["description"] or "",
                    embedding=None
                ),
                vector_score=similar["score"]
            ))
    return candidate_pairs

class DuplicatePairResult(BaseModel):
    entity1_id: str
    entity2_id: str
    justification: str

class DuplicatePairResultList(BaseModel):
    duplicates: List[DuplicatePairResult]

async def confirm_duplicates_with_openai_per_entity(
    entity: EntityNode,
    candidates: list[EntityNode],
    vector_scores: dict,
    openai_model: str,
    openai_api_key: str
) -> list[DuplicatePair]:
    """
    For a single entity and its candidate list, ask OpenAI which candidates are duplicates of the entity.
    """
    from tqdm import tqdm
    client = get_llm_client()
    confirmed = []

    if not candidates:
        return confirmed

    # Prepare prompt
    candidate_descriptions = []
    for cand in candidates:
        candidate_descriptions.append(
            f"ID: {cand.id}, Name: {cand.name}, Description: {cand.description}"
        )
    prompt = (
        f"Target Entity:\n"
        f"ID: {entity.id}\n"
        f"Name: {entity.name}\n"
        f"Description: {entity.description}\n\n"
        f"Candidates:\n" +
        "\n".join(candidate_descriptions) +
        "\n\n"
        "Return a JSON object with a 'duplicates' field, which is a list of objects. "
        "Each object should have 'candidate_id' and 'justification' fields, for each candidate you consider a duplicate of the target entity. "
        "Only include candidates that are likely duplicates."
    )

    class PerEntityDuplicateResult(BaseModel):
        candidate_id: str
        justification: str

    class PerEntityDuplicateResultList(BaseModel):
        duplicates: List[PerEntityDuplicateResult]

    try:
        completion = client.generate_structured_output(
            model_name=openai_model,
            messages=[
                {"role": "system", "content": "You are an expert at entity deduplication. Return a valid JSON object with a 'duplicates' field, which is a list of objects with 'candidate_id' and 'justification'."},
                {"role": "user", "content": prompt}
            ],
            pydantic_model=PerEntityDuplicateResultList,
            temperature=0.1
        )
        parsed = completion
        for dup in parsed.duplicates:
            cand = next((c for c in candidates if c.id == dup.candidate_id), None)
            if cand:
                score = vector_scores.get(cand.id, 0.0)
                confidence_score = round(score * 10, 1)
                reasoning = f"Vector similarity score: {score:.3f}. OpenAI: {dup.justification}"
                confirmed.append(DuplicatePair(
                    entity1_id=entity.id,
                    entity1_name=entity.name,
                    entity2_id=cand.id,
                    entity2_name=cand.name,
                    confidence_score=confidence_score,
                    reasoning=reasoning
                ))
    except Exception as e:
        logger.error(f"OpenAI batch error for entity {entity.id}: {e}")
    return confirmed

async def find_potential_duplicates(limit: int, project_id: int) -> DeduplicationResponse:
    """
    For each entity, get top N similar (N configurable), then ask OpenAI which are duplicates.
    Avoid redundant checks. Use tqdm for progress.
    """
    logger.info(f"Checking up to {limit} entities for duplicates using per-entity vector search and OpenAI confirmation...")
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
    similarity_threshold = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    top_n = int(os.getenv("VECTOR_TOP_N", "40"))

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            entities = get_recent_entities_with_embeddings(session, project_id, limit)
            if len(entities) < 2:
                return DeduplicationResponse(
                    total_entities_checked=len(entities),
                    potential_duplicates_found=0,
                    duplicates=[]
                )
            already_checked = set()
            all_duplicates = []
            for entity in tqdm(entities, desc="Deduplication (vector+OpenAI)", unit="entity"):
                # For this entity, get top N similar (excluding already checked)
                similar_entities = session.run(
                    f"""
                    CALL db.index.vector.queryNodes('person_embeddings', {top_n+1}, $embedding)
                    YIELD node, score
                    WHERE ID(node) <> $entity_id
                      AND node.project_id = $project_id
                      AND score > $threshold
                    RETURN ID(node) as id, node.name as name, node.description as description, score
                    ORDER BY score DESC
                    LIMIT {top_n}
                    """,
                    entity_id=int(entity.id),
                    project_id=project_id,
                    embedding=entity.embedding,
                    threshold=similarity_threshold
                ).data()
                candidates = []
                vector_scores = {}
                for sim in similar_entities:
                    sim_id = str(sim["id"])
                    pair_key = tuple(sorted([entity.id, sim_id]))
                    if pair_key in already_checked:
                        continue
                    already_checked.add(pair_key)
                    candidates.append(EntityNode(
                        id=sim_id,
                        name=sim["name"] or "Unknown",
                        description=sim["description"] or "",
                        embedding=None
                    ))
                    vector_scores[sim_id] = sim["score"]
                if candidates:
                    dups = await confirm_duplicates_with_openai_per_entity(
                        entity, candidates, vector_scores, openai_model, openai_api_key
                    )
                    all_duplicates.extend(dups)
        return DeduplicationResponse(
            total_entities_checked=len(entities),
            potential_duplicates_found=len(all_duplicates),
            duplicates=all_duplicates
        )
    finally:
        driver.close()


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
