from pydantic import BaseModel
from typing import Optional, List, Any, Dict


class UserBase(BaseModel):
    name: str
    email: str
    org: str
    sub: bool


class UserCreate(UserBase):
    pass


class ChangedFileReq(BaseModel):
    changedFiles: list
    pr_no: int
    owner: str
    repo: str


class PRBase(BaseModel):
    org: str
    repo: str
    pr_no: int
    branch: str
    cnt: int


# Checkpoint schemas
class CheckpointCreate(BaseModel):
    """Schema for creating a new checkpoint."""
    thread_id: str
    owner: Optional[str] = None
    repo: Optional[str] = None
    pr_number: Optional[int] = None
    current_node: str
    completed_nodes: List[str] = []
    state_data: Dict[str, Any]
    status: str = "in_progress"


class CheckpointUpdate(BaseModel):
    """Schema for updating an existing checkpoint."""
    current_node: Optional[str] = None
    completed_nodes: Optional[List[str]] = None
    state_data: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    error_message: Optional[str] = None

