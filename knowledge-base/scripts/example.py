"""
Example script demonstrating the Learnings system end-to-end.

Run this after starting Redis, Qdrant, Celery worker, and FastAPI server.
"""

import time
import requests
from datetime import datetime

# API base URL
BASE_URL = "http://localhost:8000"


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_health_checks():
    """Test health check endpoints."""
    print_section("1. Health Checks")
    
    # API health
    response = requests.get(f"{BASE_URL}/health")
    print(f"API Health: {response.json()}")
    
    # Worker health
    response = requests.get(f"{BASE_URL}/worker-health")
    print(f"Worker Health: {response.json()}")
    
    # Stats
    response = requests.get(f"{BASE_URL}/stats")
    print(f"Collection Stats: {response.json()}")


def test_ingestion():
    """Test learning ingestion with sample comments."""
    print_section("2. Ingesting Review Comments")
    
    sample_comments = [
        {
            "comment_id": "c1",
            "raw_comment": "Always use const instead of let for variables that never change. This prevents accidental reassignments and makes code intent clearer.",
            "code_snippet": "let config = { apiUrl: 'https://api.example.com' };",
            "language": "javascript",
            "source": {
                "repo_name": "acme/web-app",
                "pr_number": 1234,
                "pr_title": "Refactor config handling",
                "file_path": "src/config.js",
                "author": "coderabbit-bot",
                "reviewer": "alice",
                "timestamp": datetime.utcnow().isoformat()
            },
            "feedback_type": "accepted"
        },
        {
            "comment_id": "c2",
            "raw_comment": "Add error handling for API calls. All external requests should have try-catch blocks with proper error logging.",
            "code_snippet": "const data = await fetch(url).then(r => r.json());",
            "language": "javascript",
            "source": {
                "repo_name": "acme/web-app",
                "pr_number": 1235,
                "pr_title": "Add user API integration",
                "file_path": "src/api/users.js",
                "author": "coderabbit-bot",
                "reviewer": "bob",
                "timestamp": datetime.utcnow().isoformat()
            },
            "feedback_type": "accepted"
        },
        {
            "comment_id": "c3",
            "raw_comment": "Update dependencies regularly and run security audits. Use automated tools like Dependabot for tracking updates.",
            "code_snippet": None,
            "language": "javascript",
            "source": {
                "repo_name": "acme/web-app",
                "pr_number": 1236,
                "pr_title": "Dependency updates",
                "file_path": "package.json",
                "author": "dependabot",
                "reviewer": "alice",
                "timestamp": datetime.utcnow().isoformat()
            },
            "feedback_type": "thanked"
        },
        {
            "comment_id": "c4",
            "raw_comment": "Add type hints to all function signatures. This improves IDE support and catches type errors early.",
            "code_snippet": "def process_data(data):\n    return data.strip()",
            "language": "python",
            "source": {
                "repo_name": "acme/backend",
                "pr_number": 567,
                "pr_title": "Add data processing utility",
                "file_path": "src/utils/data.py",
                "author": "coderabbit-bot",
                "reviewer": "charlie",
                "timestamp": datetime.utcnow().isoformat()
            },
            "feedback_type": "accepted"
        },
        {
            "comment_id": "c5",
            "raw_comment": "Use environment variables for configuration instead of hardcoded values. This makes the app more secure and portable.",
            "code_snippet": "API_KEY = 'sk-1234567890'",
            "language": "python",
            "source": {
                "repo_name": "acme/backend",
                "pr_number": 568,
                "pr_title": "Add API integration",
                "file_path": "src/config.py",
                "author": "coderabbit-bot",
                "reviewer": "charlie",
                "timestamp": datetime.utcnow().isoformat()
            },
            "feedback_type": "accepted"
        }
    ]
    
    task_ids = []
    
    for comment in sample_comments:
        print(f"Ingesting: {comment['comment_id']} - {comment['raw_comment'][:60]}...")
        
        payload = {
            "comment": comment,
            "async_processing": True
        }
        
        response = requests.post(f"{BASE_URL}/learnings/ingest", json=payload)
        result = response.json()
        
        print(f"  Status: {result['status']}")
        if result.get('task_id'):
            print(f"  Task ID: {result['task_id']}")
            task_ids.append(result['task_id'])
    
    print(f"\nQueued {len(task_ids)} ingestion tasks. Waiting for processing...")
    time.sleep(10)  # Wait for Celery workers to process
    
    # Check task statuses
    print("\nChecking task statuses:")
    for task_id in task_ids:
        response = requests.get(f"{BASE_URL}/learnings/ingest/{task_id}")
        status = response.json()
        print(f"  {task_id}: {status['state']}")


def test_search():
    """Test learning search with various queries."""
    print_section("3. Searching for Learnings")
    
    queries = [
        "error handling for API calls",
        "dependency updates",
        "type hints in Python",
        "configuration management",
        "code quality best practices"
    ]
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        
        response = requests.get(
            f"{BASE_URL}/learnings/search",
            params={
                "q": query,
                "k": 3,
                "min_confidence": 0.5
            }
        )
        
        result = response.json()
        
        print(f"  Found {result['total_results']} results in {result['search_time_ms']}ms")
        
        for i, learning in enumerate(result['results'], 1):
            print(f"\n  {i}. [{learning['language']}] {learning['source']['file_path']}")
            print(f"     {learning['learning_text'][:100]}...")
            print(f"     Confidence: {learning['confidence_score']:.2f}")


def test_pr_context():
    """Test PR-specific learning retrieval."""
    print_section("4. PR Context Learning Retrieval")
    
    pr_scenarios = [
        {
            "pr_description": "Add new API endpoint for user management",
            "changed_files": ["src/api/users.js", "src/routes/api.js"],
            "repo_name": "acme/web-app"
        },
        {
            "pr_description": "Refactor data processing utilities",
            "changed_files": ["src/utils/data.py", "tests/test_data.py"],
            "repo_name": "acme/backend"
        }
    ]
    
    for scenario in pr_scenarios:
        print(f"\nPR: {scenario['pr_description']}")
        print(f"Files: {', '.join(scenario['changed_files'])}")
        
        response = requests.post(
            f"{BASE_URL}/learnings/pr-context",
            json=scenario
        )
        
        learnings = response.json()
        
        print(f"\nRetrieved {len(learnings)} relevant learnings:")
        
        for i, learning in enumerate(learnings, 1):
            print(f"\n  {i}. {learning['learning_text'][:80]}...")
            print(f"     Source: {learning['source']['repo_name']} PR#{learning['source']['pr_number']}")
            print(f"     Confidence: {learning['confidence_score']:.2f}")


def test_context_formatting():
    """Test formatted context for LLM injection."""
    print_section("5. Formatted Context for LLM")
    
    query = "best practices for API development"
    
    response = requests.post(
        f"{BASE_URL}/learnings/format-context",
        params={"query": query, "k": 3}
    )
    
    result = response.json()
    
    print(f"Query: '{query}'")
    print(f"\nFormatted Context ({result['total_learnings']} learnings):")
    print("\n" + result['formatted_context'])


def test_stats():
    """Display collection statistics."""
    print_section("6. Collection Statistics")
    
    response = requests.get(f"{BASE_URL}/stats")
    stats = response.json()
    
    print(f"Status: {stats['status']}")
    
    if 'stats' in stats:
        for key, value in stats['stats'].items():
            print(f"  {key}: {value}")


def main():
    """Run all example tests."""
    print("\n" + "="*60)
    print("  LEARNINGS SYSTEM - END-TO-END DEMO")
    print("="*60)
    print("\nMake sure the following services are running:")
    print("  1. Redis (port 6379)")
    print("  2. Qdrant (port 6333)")
    print("  3. Celery Worker (celery -A celery_worker worker)")
    print("  4. FastAPI Server (uvicorn main:app --reload)")
    print("\nPress Enter to continue...")
    input()
    
    try:
        # Run tests in sequence
        test_health_checks()
        test_ingestion()
        test_search()
        test_pr_context()
        test_context_formatting()
        test_stats()
        
        print_section("Demo Complete!")
        print("The Learnings system is working correctly. ✅")
        print("\nNext steps:")
        print("  - Integrate with your review agent")
        print("  - Add to LangGraph workflow")
        print("  - Ingest historical review data")
        print("  - Monitor with /stats endpoint")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to API server.")
        print("Make sure the FastAPI server is running:")
        print("  uvicorn main:app --reload --port 8000")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
