"""
Example usage of the Knowledge Base API
"""

import requests
import time
from datetime import datetime

API_BASE_URL = "http://localhost:8000"


def add_learning(learning_data: dict) -> dict:
    """Add a learning to the knowledge base."""
    response = requests.post(f"{API_BASE_URL}/learnings", json=learning_data)
    response.raise_for_status()
    return response.json()


def check_task_status(task_id: str) -> dict:
    """Check the status of a processing task."""
    response = requests.get(f"{API_BASE_URL}/tasks/{task_id}")
    response.raise_for_status()
    return response.json()


def wait_for_task(task_id: str, timeout: int = 30) -> dict:
    """Wait for a task to complete."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status = check_task_status(task_id)
        
        if status["status"] in ["SUCCESS", "FAILURE"]:
            return status
        
        time.sleep(1)
    
    raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")


def main():
    print("Knowledge Base API Example Usage\n")
    
    # Example 1: Add a single learning
    print("1. Adding a single learning...")
    learning = {
        "learning": "Always use type hints in Python functions for better code readability and IDE support.",
        "learnt_from": "PythonBestPractices",
        "pr": "example/repo#123",
        "file": "src/utils.py:45-60",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    result = add_learning(learning)
    print(f"   Status: {result['status']}")
    print(f"   Task ID: {result['task_id']}")
    
    # Wait for processing
    print("   Waiting for processing...")
    final_status = wait_for_task(result["task_id"])
    print(f"   Result: {final_status['result']}\n")
    
    # Example 2: Add multiple learnings
    print("2. Adding multiple learnings in batch...")
    learnings = [
        {
            "learning": "Use environment variables for configuration to keep secrets out of code.",
            "learnt_from": "SecurityTeam"
        },
        {
            "learning": "Write unit tests for all public functions to ensure code reliability.",
            "learnt_from": "QATeam"
        },
        {
            "learning": "Use meaningful commit messages that explain the 'why' not just the 'what'.",
            "learnt_from": "GitWorkflow"
        }
    ]
    
    response = requests.post(f"{API_BASE_URL}/learnings/batch", json=learnings)
    results = response.json()
    
    for idx, result in enumerate(results, 1):
        print(f"   Learning {idx}: {result['status']} (Task: {result['task_id']})")
    
    print("\n3. All learnings have been submitted!")
    print("\nYou can now query the knowledge base using main.py:")
    print("   uv run python main.py")


if __name__ == "__main__":
    try:
        # Check if API is running
        response = requests.get(f"{API_BASE_URL}/")
        print(f"Connected to: {response.json()['message']}\n")
        
        main()
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to the API.")
        print("Please ensure the API server is running:")
        print("   uv run uvicorn app:app --reload")
    except Exception as e:
        print(f"ERROR: {e}")
