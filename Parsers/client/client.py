"""
Celery Client
Submit tasks to the Celery worker for processing
"""

from celery import Celery
from typing import Dict, Any, Optional
from worker.worker import process_file, run_pipeline, run_workflow
import time

app = Celery(
    "Parsers-Client",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)


def submit_file_for_processing(file_path: str, output_dir: str = "output") -> str:
    """
    Submit a file for processing through pipeline and workflow
    
    Args:
        file_path: Path to the source file to analyze
        output_dir: Output directory for results
    
    Returns:
        Task ID for tracking
    """
    
    result = process_file.apply_async(args=[file_path, output_dir])
    print(f"Task submitted: {result.id}")
    return result.id


def submit_pipeline_only(file_path: str, output_dir: str = "output") -> str:
    """
    Submit a file for pipeline processing only (no workflow)
    
    Args:
        file_path: Path to the source file to analyze
        output_dir: Output directory for results
    
    Returns:
        Task ID for tracking
    """
    
    result = run_pipeline.apply_async(args=[file_path, output_dir]) 
    print(f"Pipeline task submitted: {result.id}")
    return result.id


def submit_workflow_only(pipeline_result: Dict[str, Any]) -> str:
    """
    Submit workflow processing with existing pipeline result
    
    Args:
        pipeline_result: Result from a previous pipeline run
    
    Returns:
        Task ID for tracking
    """
    
    result = run_workflow.apply_async(args=[pipeline_result])
    print(f"Workflow task submitted: {result.id}")
    return result.id


def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get the status and result of a task
    
    Args:
        task_id: Task ID returned from submit functions
    
    Returns:
        Dictionary with task status and result
    """
    result = app.AsyncResult(task_id)
    
    return {
        "task_id": task_id,
        "state": result.state,
        "info": result.info,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
        "result": result.result if result.ready() else None,
    }


def wait_for_task(task_id: str, timeout: int = 300, poll_interval: int = 2) -> Dict[str, Any]:
    """
    Wait for a task to complete and return the result
    
    Args:
        task_id: Task ID to wait for
        timeout: Maximum time to wait in seconds
        poll_interval: Time between status checks in seconds
    
    Returns:
        Task result
    """
    result = app.AsyncResult(task_id)
    
    print(f"Waiting for task {task_id}...")
    start_time = time.time()
    
    while not result.ready():
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"Timeout after {timeout} seconds")
            return {
                "status": "timeout",
                "task_id": task_id,
                "state": result.state,
            }
        
        print(f"  Status: {result.state} (elapsed: {elapsed:.1f}s)")
        time.sleep(poll_interval)
    
    if result.successful():
        print("Task completed successfully!")
        return result.result
    else:
        print(f"Task failed: {result.info}")
        return {
            "status": "failed",
            "task_id": task_id,
            "error": str(result.info),
        }


def revoke_task(task_id: str, terminate: bool = False) -> Dict[str, str]:
    """
    Cancel a running task
    
    Args:
        task_id: Task ID to cancel
        terminate: If True, terminate the task immediately
    
    Returns:
        Status message
    """
    app.control.revoke(task_id, terminate=terminate)
    return {
        "status": "revoked",
        "task_id": task_id,
        "terminated": terminate,
    }


if __name__ == "__main__":
    # Example usage
    print("Celery Client - Example Usage\n")
    
    # Example: Submit a file for processing
    print("Submitting file for processing...")
    task_id = submit_file_for_processing("example.py", "output")
    
    # Wait for result
    result = wait_for_task(task_id)
    
    print("\nFinal Result:")
    print(result)
