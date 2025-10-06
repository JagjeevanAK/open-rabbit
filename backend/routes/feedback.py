from fastapi import APIRouter

router = APIRouter(
    prefix="/feedback",
    tags=["feedback"]
)

@router.post("/comment")
def comment():
    pass

@router.post("/accept")
def sugg_commit():
    pass
