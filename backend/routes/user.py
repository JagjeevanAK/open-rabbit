from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.database import get_db
from db import crud, schemas

router = APIRouter(
    prefix="/users",
    tags=["users"]
)

@router.post("/new_install")
def get_user(user :schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.create_install(db, user=user)
    return db_user
    
@router.post("/signin")
async def signin(body: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_name=body.name)
    
    if db_user:
        return {"status": "Successful signIn"}
    return {"status": "User does not exist in db"}

@router.post("/signup")
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.create_user(db, user=user)
    return db_user