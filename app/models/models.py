import re
from pydantic import BaseModel, validator
from typing import List, Optional, Dict, Any

# Person models
class PersonBase(BaseModel):
    name: str
    description: str
    age: Optional[int] = None
    email: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: Optional[str] = None
    embedding: Optional[list[float]] = None  # Vector embedding for deduplication

class PersonCreate(PersonBase):
    pass

class PersonUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    age: Optional[int] = None
    email: Optional[str] = None

class Person(PersonBase):
    id: str
    embedding: Optional[list[float]] = None

    class Config:
        orm_mode = True

# Relationship models
class RelationshipCreate(BaseModel):
    person1_id: str
    person2_id: str
    relationship_type: str
    
    @validator('relationship_type')
    def validate_relationship_type(cls, v):
        # Allow letters, numbers, spaces and underscores
        if not re.match(r'^[a-zA-Z0-9_ ]+$', v):
            raise ValueError('Relationship type can only contain letters, numbers, spaces, and underscores')
        return v

# Knowledge Graph models
class TextInput(BaseModel):
    text: str

class EntityResponse(BaseModel):
    entity_id: str
    label: str
    type: str
    description: str

class RelationshipResponse(BaseModel):
    source_id: str
    target_id: str
    label: str

class KnowledgeGraph(BaseModel):
    entities: List[EntityResponse]
    relationships: List[RelationshipResponse]

# Deduplication models
class DuplicatePair(BaseModel):
    entity1_id: str
    entity1_name: str
    entity2_id: str
    entity2_name: str
    confidence_score: float
    reasoning: str

class DeduplicationRequest(BaseModel):
    limit: int = 100

class DeduplicationResponse(BaseModel):
    duplicates: List[DuplicatePair]
    total_entities_checked: int
    potential_duplicates_found: int
