from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.postgres_db import Base

# Project-KnowledgeGraph association table (for future use)
project_kg_association = Table(
    'project_kg_association',
    Base.metadata,
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
    Column('kg_id', Integer, ForeignKey('knowledge_graphs.id'), primary_key=True)
)

# Project model
class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    description = Column(Text, nullable=True)
    creator_email = Column(String(255), index=True)
    authorization_group = Column(String(255), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship for future integration with knowledge graphs
    # knowledge_graphs = relationship("KnowledgeGraph", secondary=project_kg_association, back_populates="projects")
    
    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', creator='{self.creator_email}')>"

# Knowledge Graph model placeholder for future integration
class KnowledgeGraph(Base):
    __tablename__ = "knowledge_graphs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    description = Column(Text, nullable=True)
    creator_email = Column(String(255), index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship with project
    project = relationship("Project")
    # projects = relationship("Project", secondary=project_kg_association, back_populates="knowledge_graphs")
    
    def __repr__(self):
        return f"<KnowledgeGraph(id={self.id}, name='{self.name}')>"

# User model
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships example
    # items = relationship("Item", back_populates="owner")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"

# Example model for an Item
class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships example
    # owner = relationship("User", back_populates="items")
    # tags = relationship("Tag", secondary=tag_association, back_populates="items")
    
    def __repr__(self):
        return f"<Item(id={self.id}, title='{self.title}')>"

# Example model for a Tag
class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True)
    
    # Relationships example
    # items = relationship("Item", secondary=tag_association, back_populates="tags")
    
    def __repr__(self):
        return f"<Tag(id={self.id}, name='{self.name}')>"
