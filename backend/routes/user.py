from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.database import get_db
from db import crud
from schemas import UserCreate

router = APIRouter(
    prefix="/users",
    tags=["users"]
)

@router.post("/new_install")
def new_install(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new GitHub app installation"""
    try:
        existing_install = db.query(crud.models.NewInstall).filter(
            crud.models.NewInstall.name == user.name
        ).first()

        if existing_install:
            return {
                "status": "already_exists",
                "message": f"Installation for {user.name} already exists",
                "data": existing_install
            }

        db_user = crud.create_install(db, user=user)
        return {
            "status": "success",
            "message": f"Successfully registered installation for {user.name}",
            "data": db_user
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to register installation: {str(e)}"
        }

@router.post("/signin")
async def signin(body: UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_name=body.name)

    if db_user:
        return {"status": "Successful signIn"}
    return {"status": "User does not exist in db"}

@router.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    db_user = crud.create_user(db, user=user)
    return db_user

@router.get("/check-owner/{owner_name}")
def check_owner(owner_name: str, db: Session = Depends(get_db)):
    """Check if owner exists in database"""
    exists = crud.check_owner_exists(db, owner_name=owner_name)
    return {"owner": owner_name, "authorized": exists}
