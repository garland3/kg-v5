from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.postgres_db import Base

# Example of a many-to-many association table
# tag_association = Table(
#     'tag_association',
#     Base.metadata,
#     Column('item_id', Integer, ForeignKey('items.id'), primary_key=True),
#     Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
# )

# Example model for a User
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
