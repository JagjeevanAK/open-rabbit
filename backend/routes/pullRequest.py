from fastapi import APIRouter

router = APIRouter(
    prefix="/feature"
    tags =["feature"]
)

@router.post("/unit_test")
def unitTest():
    pass