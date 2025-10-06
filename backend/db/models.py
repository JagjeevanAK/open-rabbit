from .database import Base
from sqlalchemy import Column, Boolean, Integer, String

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, index=True, primary_key=True)
    name = Column(String, index=True)
    email = Column(String, index=True)
    sub = Column(Boolean, index=True, default=False)
    org = Column(String, index=True)
    
class PullRequest(Base):
    __tablename__ = "pull_request"
    id = Column(Integer, index=True, primary_key=True)
    org = Column(String, index=True)
    repo = Column(String, index=True)
    pr_no = Column(Integer, index=True)
    branch = Column(String, index=True)
    cnt = Column(Integer, index=True, default=1)