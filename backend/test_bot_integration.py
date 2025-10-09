"""
Integration Test: Bot Unit Test Generation

This script demonstrates the complete flow of unit test generation
triggered by the GitHub bot.
"""

import requests
import time
import json

BACKEND_URL = "http://localhost:8080"


def test_bot_webhook_health():
    """Test that bot webhook endpoint is healthy"""
    print("Testing bot webhook health...")
    response = requests.get(f"{BACKEND_URL}/bot/health")
    assert response.status_code == 200
    data = response.json()
    print(f"✅ Health check passed: {data}")
    return data


def test_create_unit_tests():
    """Simulate bot triggering unit test generation"""
    print("\nSimulating /create-unit-test command...")
    
    payload = {
        "owner": "testuser",
        "repo": "test-repo",
        "issue_number": 42,
        "branch": "main",
        "installation_id": 12345,
        "comment_id": 67890
    }
    
    response = requests.post(
        f"{BACKEND_URL}/bot/create-unit-tests",
        json=payload
    )
    
    assert response.status_code == 200
    data = response.json()
    
    print(f"✅ Task created:")
    print(f"   Task ID: {data['task_id']}")
    print(f"   Status: {data['status']}")
    print(f"   Test Branch: {data['test_branch']}")
    
    return data["task_id"], data["test_branch"]


def test_poll_task_status(task_id: str, max_attempts: int = 60):
    """Poll task status until completion or timeout"""
    print(f"\nPolling task status (task_id: {task_id})...")
    
    for attempt in range(1, max_attempts + 1):
        response = requests.get(f"{BACKEND_URL}/bot/task-status/{task_id}")
        
        if response.status_code == 404:
            print(f"❌ Task not found")
            return None
        
        assert response.status_code == 200
        data = response.json()
        status = data["status"]
        
        print(f"   Attempt {attempt}/{max_attempts}: Status = {status}")
        
        if status == "completed":
            print(f"✅ Task completed!")
            print(f"   Result: {json.dumps(data.get('result', {}), indent=2)}")
            return data
        
        elif status == "failed":
            print(f"❌ Task failed!")
            print(f"   Error: {data.get('error', 'Unknown error')}")
            return data
        
        time.sleep(5)
    
    print(f"⏱️ Timeout after {max_attempts * 5} seconds")
    return None


def test_list_tasks():
    """List all bot tasks"""
    print("\nListing all bot tasks...")
    response = requests.get(f"{BACKEND_URL}/bot/tasks")
    assert response.status_code == 200
    data = response.json()
    
    print(f"✅ Total tasks: {data['total']}")
    for task in data['tasks']:
        print(f"   - {task['task_id']}: {task['status']} ({task['owner']}/{task['repo']})")
    
    return data


def main():
    """Run integration tests"""
    print("=" * 60)
    print("Bot Integration Test - Unit Test Generation")
    print("=" * 60)
    
    try:
        # Test 1: Health check
        test_bot_webhook_health()
        
        # Test 2: Create unit tests
        task_id, test_branch = test_create_unit_tests()
        
        # Test 3: Poll status
        result = test_poll_task_status(task_id, max_attempts=10)
        
        # Test 4: List all tasks
        test_list_tasks()
        
        print("\n" + "=" * 60)
        print("Integration test completed!")
        print("=" * 60)
        
        if result and result["status"] == "completed":
            print("\n✅ All tests passed!")
            print(f"\nNext steps:")
            print(f"1. Tests should be on branch: {test_branch}")
            print(f"2. Bot should create PR automatically")
            print(f"3. Check GitHub for the new pull request")
        else:
            print("\n⚠️  Tests completed with warnings")
            print("Check the task status for more details")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
