from pydantic import BaseModel

class UserBase(BaseModel):
    name: str
    email: str
    org: str
    sub: bool

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int

    class Config:
        orm_mode = True

class PRBase(BaseModel):
    org: str
    repo: str
    pr_no: int
    branch: str
    cnt: int

class PRCreate(PRBase):
    pass

class PRupdate(PRBase):
    pass