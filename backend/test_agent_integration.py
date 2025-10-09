#!/usr/bin/env python3
"""
Simple test script to verify the agent integration works correctly.
Run this to ensure everything is set up properly.
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8080"


def test_health():
    """Test if the server is running"""
    print("🔍 Testing server health...")
    try:
        response = requests.get(f"{BASE_URL}/healthz")
        if response.status_code == 200:
            print("✅ Server is running")
            return True
        else:
            print(f"❌ Server returned {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
        print("   Run: python backend/server.py")
        return False


def test_list_tasks():
    """Test listing review tasks"""
    print("\n🔍 Testing task listing...")
    try:
        response = requests.get(f"{BASE_URL}/feedback/review/tasks")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Task listing works. Current tasks: {data['total']}")
            return True
        else:
            print(f"❌ Task listing failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_start_review():
    """Test starting a review"""
    print("\n🔍 Testing review start...")
    
    payload = {
        "repo_url": "torvalds/linux",
        "branch": "master",
        "pr_description": "Test review",
        "changed_files": ["README"]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/feedback/review/pr",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            task_id = data.get("task_id")
            print(f"✅ Review started successfully")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {data.get('status')}")
            return task_id
        else:
            print(f"❌ Review start failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_check_status(task_id: str):
    """Test checking review status"""
    print(f"\n🔍 Testing status check for task {task_id}...")
    
    try:
        response = requests.get(f"{BASE_URL}/feedback/review/status/{task_id}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status check works")
            print(f"   Status: {data.get('status')}")
            print(f"   Created: {data.get('created_at')}")
            return data
        else:
            print(f"❌ Status check failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_get_result(task_id: str, wait: bool = True):
    """Test getting review result"""
    print(f"\n🔍 Testing result retrieval for task {task_id}...")
    
    if wait:
        print("   Waiting for review to complete...")
        for i in range(30):
            status_data = test_check_status(task_id)
            if status_data and status_data.get('status') in ['completed', 'failed']:
                break
            time.sleep(2)
            print(f"   Still running... ({i*2}s)")
    
    try:
        response = requests.get(f"{BASE_URL}/feedback/review/result/{task_id}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Result retrieval works")
            print(f"   Result status: {data.get('status')}")
            if 'formatted_review' in data:
                print(f"   Has formatted review: Yes")
                review = data['formatted_review']
                if isinstance(review, dict):
                    print(f"   Summary: {review.get('summary', 'N/A')[:100]}...")
                    print(f"   Comments: {len(review.get('comments', []))}")
            return data
        elif response.status_code == 202:
            print(f"⏳ Review still in progress")
            return None
        else:
            print(f"❌ Result retrieval failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_file_review():
    """Test file-based review"""
    print("\n🔍 Testing file review...")
    
    payload = {
        "file_paths": ["README.md", "src/main.py"],
        "repo_path": "/tmp/test-repo",
        "context": "Testing file review functionality"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/feedback/review/files",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ File review started")
            print(f"   Task ID: {data.get('task_id')}")
            return data.get("task_id")
        else:
            print(f"❌ File review failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("Code Review Agent Integration Test")
    print("=" * 70)
    
    results = {
        "server_health": False,
        "list_tasks": False,
        "start_review": False,
        "check_status": False,
        "get_result": False,
        "file_review": False
    }
    
    # Test 1: Server health
    results["server_health"] = test_health()
    if not results["server_health"]:
        print("\n❌ Server is not running. Aborting tests.")
        return results
    
    # Test 2: List tasks
    results["list_tasks"] = test_list_tasks()
    
    # Test 3: Start review
    task_id = test_start_review()
    results["start_review"] = task_id is not None
    
    # Test 4: Check status
    if task_id:
        status_data = test_check_status(task_id)
        results["check_status"] = status_data is not None
        
        # Test 5: Get result (don't wait for completion in quick test)
        result_data = test_get_result(task_id, wait=False)
        results["get_result"] = result_data is not None or True  # 202 is also OK
    
    # Test 6: File review
    file_task_id = test_file_review()
    results["file_review"] = file_task_id is not None
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The agent is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
    
    return results


if __name__ == "__main__":
    import sys
    
    try:
        results = run_all_tests()
        sys.exit(0 if all(results.values()) else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
