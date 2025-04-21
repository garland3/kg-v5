import os
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, UploadFile
from app.utils.llm import get_llm_client
from dotenv import load_dotenv

# --- Configuration ---

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get model from environment
model = os.getenv("OPENAI_MODEL", "gpt-4")
logger.info(f"Using OpenAI model: {model}")

# --- Pydantic Models ---
# Define the structure for an entity in the knowledge graph
class EntityBase(BaseModel):
    entity_id: str = Field(..., description="Unique identifier for the entity within the text context.")
    label: str = Field(..., description="The name or label of the entity.")
    type: str = Field(..., description="The type or category of the entity (e.g., Person, Organization, Location).")
    description: str = Field(..., description="A brief description of the entity. Max 2 sentences. Try to give a desciption that is not about their relationships, but cool facts about the entity itself which would allow easily reidentification in another context..")

class EntityCreate(EntityBase):
    pass

class EntityResponse(EntityBase):
    project_id: Optional[int] = None

    class Config:
        orm_mode = True

# Define the structure for a relationship between entities
class RelationshipBase(BaseModel):
    source_id: str = Field(..., description="The ID of the source entity for the relationship.")
    target_id: str = Field(..., description="The ID of the target entity for the relationship.")
    label: str = Field(..., description="The description or type of the relationship (e.g., works_at, located_in).")

class RelationshipCreate(RelationshipBase):
    pass

class RelationshipResponse(RelationshipBase):
    project_id: Optional[int] = None

    class Config:
        orm_mode = True

# Define the overall structure for the knowledge graph output
class KnowledgeGraph(BaseModel):
    entities: List[EntityResponse] = Field(..., description="A list of extracted entities.")
    relationships: List[RelationshipResponse] = Field(..., description="A list of extracted relationships connecting the entities.")

# Project models
class ProjectBase(BaseModel):
    name: str = Field(..., description="Name of the project")
    description: Optional[str] = Field(None, description="Optional description of the project")

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: int
    created_at: str
    entities: List[EntityResponse] = []
    relationships: List[RelationshipResponse] = []

    class Config:
        orm_mode = True

# Define the input model for plain text requests
class TextInput(BaseModel):
    text: str = Field(..., min_length=1, description="The raw text to process.")
    # project_id removed, will be passed as function argument

# --- OpenAI Interaction ---
async def extract_knowledge_graph_from_text(text: str, project_id: Optional[int] = None) -> KnowledgeGraph: # Added project_id parameter
    """
    Extracts entities and relationships from text using OpenAI's API.
    Focuses ONLY on entities of type 'Person'.
    The project_id is currently not used in the extraction logic itself,
    but is accepted for consistency with the calling routes.
    """
    logger.info(f"Extracting KG from text (length: {len(text)})...")

    try:
        # Create the prompt for OpenAI
        prompt = f"""Extract a knowledge graph from the following text. 
        IMPORTANT: Identify ONLY people as entities (no organizations, locations, or other entity types).
        Focus exclusively on relationships between people.
        Return the results in a structured format matching the provided schema.

        Text to analyze:
        {text}

        Instructions:
        1. Identify all significant people (individuals) in the text
        2. For each person, assign a unique ID, label, and type ('Person')
        3. Identify relationships between these people (e.g., 'friend_of', 'married_to', 'colleague_of', etc.)
        4. Return the results in the specified JSON format
        5. ONLY include entities of type 'Person' - do not include organizations, locations, or other entity types
        """

        client = get_llm_client()
        completion = client.generate_structured_output(
            model_name=model,
            messages=[
                {"role": "system", "content": "You are an expert at extracting structured knowledge graphs from unstructured text. Return a valid JSON object with 'entities' and 'relationships' fields."},
                {"role": "user", "content": prompt}
            ],
            pydantic_model=KnowledgeGraph,
            temperature=0.1
        )

        # Filter entities to include only those of type 'Person'
        parsed_response = completion
        parsed_response.entities = [entity for entity in parsed_response.entities if entity.type == "Person"]

        return parsed_response

    except Exception as e:
        logger.error(f"Error extracting knowledge graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to extract knowledge graph: {str(e)}")

# --- Helper Function for File Processing ---
async def read_file_content(file: UploadFile) -> str:
    """Reads content from uploaded file."""
    logger.info(f"Reading content from file: {file.filename}, content type: {file.content_type}")
    if file.content_type == "text/plain":
        contents = await file.read()
        return contents.decode("utf-8")
    elif file.content_type == "application/pdf":
        logger.warning("PDF processing not implemented yet. Requires 'pypdf2'.")
        raise HTTPException(status_code=501, detail="PDF processing not yet implemented.")
    elif file.content_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
        logger.warning("DOCX processing not implemented yet. Requires 'python-docx'.")
        raise HTTPException(status_code=501, detail="DOCX processing not yet implemented.")
    else:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.content_type}")
