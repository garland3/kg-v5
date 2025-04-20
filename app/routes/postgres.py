from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from pydantic import BaseModel

from app.postgres_db import get_postgres_db
from app.models.postgres_models import User, Item, Tag

router = APIRouter(
    prefix="/postgres",
    tags=["postgres"],
    responses={404: {"description": "Not found"}},
)

# Pydantic models for request/response
class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    
    class Config:
        from_attributes = True

class ItemCreate(BaseModel):
    title: str
    description: Optional[str] = None

class ItemResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    owner_id: int
    
    class Config:
        from_attributes = True

# User routes
@router.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_postgres_db)):
    """Create a new user in the PostgreSQL database"""
    # In a real app, you would hash the password
    hashed_password = user.password + "_hashed"  # This is just a placeholder
    
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )

@router.get("/users/", response_model=List[UserResponse])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_postgres_db)):
    """Get a list of users from the PostgreSQL database"""
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.get("/users/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_postgres_db)):
    """Get a specific user by ID from the PostgreSQL database"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

# Item routes
@router.post("/users/{user_id}/items/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item_for_user(user_id: int, item: ItemCreate, db: Session = Depends(get_postgres_db)):
    """Create a new item for a specific user in the PostgreSQL database"""
    # Check if user exists
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create item
    db_item = Item(
        title=item.title,
        description=item.description,
        owner_id=user_id
    )
    
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.get("/items/", response_model=List[ItemResponse])
def read_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_postgres_db)):
    """Get a list of items from the PostgreSQL database"""
    items = db.query(Item).offset(skip).limit(limit).all()
    return items
