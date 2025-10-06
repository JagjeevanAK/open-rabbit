from fastapi import APIRouter
from db.crud import create_pr, update_pr

router = APIRouter(
    prefix="/events",
    tags=["events"]
)

@router.post("/")
def event():
    pass

@router.post("/new_commits")
def commits():
    pass