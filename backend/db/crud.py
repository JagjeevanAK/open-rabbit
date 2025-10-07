from sqlalchemy.orm import Session
from . import models, schemas

def get_user(db: Session, user_name: str):
    return db.query(models.User).filter(models.User.name == user_name).first()

# def get_users(db: Session, skip: int = 0, limit: int = 10):
#     return db.query(models.User).offset(skip).limit(limit).all()

def create_install(db:Session, user: schemas.UserCreate):
    new_user = models.NewInstall(name=user.name, org=user.org)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(name=user.name, email=user.email, org=user.org, sub=user.sub)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_pr(db: Session, pr: schemas.PRBase):
    pr_data = models.PullRequest(org= pr.org, repo = pr.repo, pr_no=pr.pr_no, branch=pr.branch)
    db.add(pr_data)
    db.commit()
    db.refresh(pr_data)
    return pr_data
    
def update_pr(db: Session, pr_no: schemas.PRBase):
    pr_data = db.query(models.PullRequest).filter(models.PullRequest.pr_no == pr_no).first()

    if not pr_data:
        return None  
    
    setattr(pr_data, 'cnt', pr_data.cnt + 1)
    db.commit()
    db.refresh(pr_data)
    return pr_data

def insert_files(db: Session, payload: schemas.ChangedFileReq):
    files_data = db.query(models.PullRequest).filter(models.PullRequest.pr_no == payload.pr_no).first()
    
    if not files_data:
        return None  
    
    setattr(files_data, 'changed_files', payload.changedFiles)
    db.commit()
    db.refresh(files_data)