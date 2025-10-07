from fastapi import APIRouter, Depends
from db import models, crud, schemas
from db.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/events",
    tags=["events"]
)

ReviewFiles= [] 

@router.post("/")
def event(pr:schemas.PRBase, db: Session = Depends(get_db)):
    return crud.create_pr(db=db, pr=pr)

@router.post("/new_commits")
def commits( pr_no: schemas.PRBase, db: Session = Depends(get_db)):
    return crud.update_pr(db=db, pr_no=pr_no)

@router.post("/changed_files")
def change_files(res: schemas.ChangedFileReq, db: Session = Depends(get_db)):
    crud.insert_files(db=db, payload=res)
    ReviewFiles.append(res.changedFiles)