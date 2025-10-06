from fastapi import APIRouter
from pydantic import BaseModel
from db.crud import create_user, get_user
from typing import Optional

router = APIRouter(
    prefix="/users",
    tags=["users"]
)
class User(BaseModel):
    name: str
    email: str
    org: Optional[str] = None
    sub: Optional[str] = None


@router.post("/new_install")
def get_user():
    
    pass

@router.post("/signin")
async def signin(body= User):
    get_user(user_name= body.name)
    pass

@router.post("/signup")
def signup():
    pass