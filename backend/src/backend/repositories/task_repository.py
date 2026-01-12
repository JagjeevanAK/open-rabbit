"""
Task Repository - Handles task state management.

This repository encapsulates all task storage and CRUD operations.
Currently uses in-memory storage, but can be easily swapped for Redis/DB.
"""
from datetime import datetime
from typing import Dict, Any, Optional, List


class TaskRepository:
    """
    Repository for managing bot task state.
    
    This is a singleton that manages task state in memory.
    Could be extended to use Redis, PostgreSQL, etc.
    """
    
    _instance: Optional["TaskRepository"] = None
    _tasks: Dict[str, Dict[str, Any]] = {}
    
    def __new__(cls) -> "TaskRepository":
        """Singleton pattern to ensure one task store."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks = {}
        return cls._instance
    
    def create_review_task(
        self,
        task_id: str,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> Dict[str, Any]:
        """
        Create a new review task.
        
        Args:
            task_id: Unique task identifier
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            The created task record
        """
        task = {
            "status": "pending",
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
        }
        self._tasks[task_id] = task
        return task
    
    def create_unit_test_task(
        self,
        task_id: str,
        owner: str,
        repo: str,
        issue_number: int,
        test_branch: str,
    ) -> Dict[str, Any]:
        """
        Create a new unit test generation task.
        
        Args:
            task_id: Unique task identifier
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            test_branch: Branch for generated tests
            
        Returns:
            The created task record
        """
        task = {
            "status": "pending",
            "owner": owner,
            "repo": repo,
            "issue_number": issue_number,
            "test_branch": test_branch,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
        }
        self._tasks[task_id] = task
        return task
    
    def create_pr_test_task(
        self,
        task_id: str,
        owner: str,
        repo: str,
        pr_number: int,
        branch: str,
    ) -> Dict[str, Any]:
        """
        Create a new PR unit test generation task.
        
        Args:
            task_id: Unique task identifier
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            branch: PR branch name
            
        Returns:
            The created task record
        """
        task = {
            "status": "pending",
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
            "branch": branch,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
        }
        self._tasks[task_id] = task
        return task
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task record or None if not found
        """
        return self._tasks.get(task_id)
    
    def task_exists(self, task_id: str) -> bool:
        """Check if a task exists."""
        return task_id in self._tasks
    
    def update_status(self, task_id: str, status: str) -> None:
        """
        Update task status.
        
        Args:
            task_id: Task identifier
            status: New status (pending, running, completed, failed)
        """
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = status
    
    def complete_task(self, task_id: str, result: Dict[str, Any]) -> None:
        """
        Mark task as completed with result.
        
        Args:
            task_id: Task identifier
            result: Task result data
        """
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = "completed"
            self._tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
            self._tasks[task_id]["result"] = result
    
    def fail_task(self, task_id: str, error: str) -> None:
        """
        Mark task as failed with error.
        
        Args:
            task_id: Task identifier
            error: Error message
        """
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
            self._tasks[task_id]["error"] = error
    
    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if deleted, False if not found
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False
    
    def list_tasks(
        self, 
        status: Optional[str] = None, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List tasks, optionally filtered by status.
        
        Args:
            status: Filter by status (optional)
            limit: Maximum number of tasks to return
            
        Returns:
            List of task records
        """
        tasks = []
        
        for task_id, task in list(self._tasks.items())[-limit:]:
            if status is None or task["status"] == status:
                tasks.append({
                    "task_id": task_id,
                    "status": task["status"],
                    "owner": task["owner"],
                    "repo": task["repo"],
                    "created_at": task["created_at"],
                    "completed_at": task.get("completed_at"),
                })
        
        return tasks
    
    def count_tasks(self, status: Optional[str] = None) -> int:
        """
        Count tasks, optionally filtered by status.
        
        Args:
            status: Filter by status (optional)
            
        Returns:
            Number of matching tasks
        """
        if status is None:
            return len(self._tasks)
        
        return sum(1 for task in self._tasks.values() if task["status"] == status)


# Default singleton instance
task_repository = TaskRepository()
