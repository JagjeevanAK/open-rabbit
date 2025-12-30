from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import json
from . import models, schemas

def get_user(db: Session, user_name: str):
    return db.query(models.User).filter(models.User.name == user_name).first()

def check_owner_exists(db: Session, owner_name: str):
    """Check if owner exists in either User or NewInstall table"""
    user_exists = db.query(models.User).filter(models.User.name == owner_name).first()
    if user_exists:
        return True
    install_exists = db.query(models.NewInstall).filter(models.NewInstall.name == owner_name).first()
    return install_exists is not None

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


# ============ Checkpoint CRUD Operations ============

def create_checkpoint(
    db: Session,
    checkpoint: schemas.CheckpointCreate
) -> models.AgentCheckpoint:
    """
    Create a new checkpoint for an agent workflow.
    
    Args:
        db: Database session
        checkpoint: Checkpoint data
        
    Returns:
        Created checkpoint model
    """
    db_checkpoint = models.AgentCheckpoint(
        thread_id=checkpoint.thread_id,
        owner=checkpoint.owner,
        repo=checkpoint.repo,
        pr_number=checkpoint.pr_number,
        current_node=checkpoint.current_node,
        completed_nodes=json.dumps(checkpoint.completed_nodes),
        state_data=json.dumps(checkpoint.state_data, default=str),
        status=checkpoint.status,
    )
    db.add(db_checkpoint)
    db.commit()
    db.refresh(db_checkpoint)
    return db_checkpoint


def get_checkpoint_by_thread_id(
    db: Session,
    thread_id: str
) -> Optional[models.AgentCheckpoint]:
    """
    Get a checkpoint by thread ID.
    
    Args:
        db: Database session
        thread_id: The workflow thread ID
        
    Returns:
        Checkpoint model or None
    """
    return db.query(models.AgentCheckpoint).filter(
        models.AgentCheckpoint.thread_id == thread_id
    ).first()


def get_checkpoint_by_pr(
    db: Session,
    owner: str,
    repo: str,
    pr_number: int,
    status: Optional[str] = None
) -> Optional[models.AgentCheckpoint]:
    """
    Get the most recent checkpoint for a PR.
    
    Args:
        db: Database session
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        status: Optional status filter
        
    Returns:
        Most recent checkpoint or None
    """
    query = db.query(models.AgentCheckpoint).filter(
        models.AgentCheckpoint.owner == owner,
        models.AgentCheckpoint.repo == repo,
        models.AgentCheckpoint.pr_number == pr_number,
    )
    
    if status:
        query = query.filter(models.AgentCheckpoint.status == status)
    
    return query.order_by(models.AgentCheckpoint.created_at.desc()).first()


def update_checkpoint(
    db: Session,
    thread_id: str,
    update_data: schemas.CheckpointUpdate
) -> Optional[models.AgentCheckpoint]:
    """
    Update an existing checkpoint.
    
    Args:
        db: Database session
        thread_id: The workflow thread ID
        update_data: Fields to update
        
    Returns:
        Updated checkpoint or None
    """
    checkpoint = get_checkpoint_by_thread_id(db, thread_id)
    if not checkpoint:
        return None
    
    if update_data.current_node is not None:
        checkpoint.current_node = update_data.current_node
    
    if update_data.completed_nodes is not None:
        checkpoint.completed_nodes = json.dumps(update_data.completed_nodes)
    
    if update_data.state_data is not None:
        checkpoint.state_data = json.dumps(update_data.state_data, default=str)
    
    if update_data.status is not None:
        checkpoint.status = update_data.status
    
    if update_data.error_message is not None:
        checkpoint.error_message = update_data.error_message
    
    db.commit()
    db.refresh(checkpoint)
    return checkpoint


def upsert_checkpoint(
    db: Session,
    checkpoint: schemas.CheckpointCreate
) -> models.AgentCheckpoint:
    """
    Create or update a checkpoint (upsert).
    
    Args:
        db: Database session
        checkpoint: Checkpoint data
        
    Returns:
        Created or updated checkpoint
    """
    existing = get_checkpoint_by_thread_id(db, checkpoint.thread_id)
    
    if existing:
        update_data = schemas.CheckpointUpdate(
            current_node=checkpoint.current_node,
            completed_nodes=checkpoint.completed_nodes,
            state_data=checkpoint.state_data,
            status=checkpoint.status,
        )
        return update_checkpoint(db, checkpoint.thread_id, update_data)
    else:
        return create_checkpoint(db, checkpoint)


def mark_checkpoint_completed(
    db: Session,
    thread_id: str,
    final_state: Dict[str, Any]
) -> Optional[models.AgentCheckpoint]:
    """
    Mark a checkpoint as completed with final state.
    
    Args:
        db: Database session
        thread_id: The workflow thread ID
        final_state: Final workflow state
        
    Returns:
        Updated checkpoint or None
    """
    return update_checkpoint(db, thread_id, schemas.CheckpointUpdate(
        status="completed",
        state_data=final_state,
        current_node="complete",
    ))


def mark_checkpoint_failed(
    db: Session,
    thread_id: str,
    error_message: str,
    current_state: Optional[Dict[str, Any]] = None
) -> Optional[models.AgentCheckpoint]:
    """
    Mark a checkpoint as failed with error message.
    
    Args:
        db: Database session
        thread_id: The workflow thread ID
        error_message: Error description
        current_state: Current state at failure
        
    Returns:
        Updated checkpoint or None
    """
    update = schemas.CheckpointUpdate(
        status="failed",
        error_message=error_message,
    )
    if current_state:
        update.state_data = current_state
    
    return update_checkpoint(db, thread_id, update)


def delete_checkpoint(db: Session, thread_id: str) -> bool:
    """
    Delete a checkpoint.
    
    Args:
        db: Database session
        thread_id: The workflow thread ID
        
    Returns:
        True if deleted, False if not found
    """
    checkpoint = get_checkpoint_by_thread_id(db, thread_id)
    if checkpoint:
        db.delete(checkpoint)
        db.commit()
        return True
    return False


def cleanup_old_checkpoints(
    db: Session,
    days_old: int = 7,
    status: Optional[str] = "completed"
) -> int:
    """
    Clean up old checkpoints.
    
    Args:
        db: Database session
        days_old: Delete checkpoints older than this
        status: Only delete checkpoints with this status
        
    Returns:
        Number of checkpoints deleted
    """
    from datetime import datetime, timedelta
    
    cutoff = datetime.utcnow() - timedelta(days=days_old)
    query = db.query(models.AgentCheckpoint).filter(
        models.AgentCheckpoint.created_at < cutoff
    )
    
    if status:
        query = query.filter(models.AgentCheckpoint.status == status)
    
    count = query.delete()
    db.commit()
    return count


def get_resumable_checkpoints(
    db: Session,
    owner: Optional[str] = None,
    repo: Optional[str] = None
) -> List[models.AgentCheckpoint]:
    """
    Get all checkpoints that can be resumed (in_progress or failed).
    
    Args:
        db: Database session
        owner: Optional owner filter
        repo: Optional repo filter
        
    Returns:
        List of resumable checkpoints
    """
    query = db.query(models.AgentCheckpoint).filter(
        models.AgentCheckpoint.status.in_(["in_progress", "failed"])
    )
    
    if owner:
        query = query.filter(models.AgentCheckpoint.owner == owner)
    if repo:
        query = query.filter(models.AgentCheckpoint.repo == repo)
    
    return query.order_by(models.AgentCheckpoint.created_at.desc()).all()


def parse_checkpoint_state(checkpoint: models.AgentCheckpoint) -> Dict[str, Any]:
    """
    Parse checkpoint state data from JSON.
    
    Args:
        checkpoint: Checkpoint model
        
    Returns:
        Parsed state dictionary
    """
    return {
        "thread_id": checkpoint.thread_id,
        "current_node": checkpoint.current_node,
        "completed_nodes": json.loads(checkpoint.completed_nodes) if checkpoint.completed_nodes else [],
        "state_data": json.loads(checkpoint.state_data) if checkpoint.state_data else {},
        "status": checkpoint.status,
        "error_message": checkpoint.error_message,
    }