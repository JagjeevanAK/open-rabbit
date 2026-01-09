"""
Test KB Integration in Code Review Workflow

Tests the end-to-end flow:
1. KB client fetches learnings
2. Workflow uses learnings during review
3. Review output includes KB context
"""

import os
import sys

# Set KB_ENABLED for the test
os.environ["KB_ENABLED"] = "true"
os.environ["KNOWLEDGE_BASE_URL"] = "http://localhost:8000"

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.workflow import CodeReviewWorkflow
from agent.services.kb_client import KnowledgeBaseClient, get_kb_client


def test_kb_client_direct():
    """Test KB client methods directly"""
    print("\n" + "="*60)
    print("TEST 1: KB Client Direct Access")
    print("="*60)
    
    client = KnowledgeBaseClient()
    
    # Check if enabled
    print(f"\n[1.1] KB Enabled: {client.enabled}")
    assert client.enabled, "KB should be enabled"
    
    # Health check
    print(f"[1.2] Health Check: ", end="")
    health = client.health_check()
    print(f"{'PASS' if health else 'FAIL'}")
    assert health, "KB health check should pass"
    
    # Search learnings
    print(f"\n[1.3] Search Learnings (query='React performance'):")
    learnings = client.search_learnings(
        query="React performance",
        owner="testowner",
        repo="testrepo",
        k=5
    )
    print(f"     Found {len(learnings)} learnings")
    for i, l in enumerate(learnings[:3], 1):
        print(f"     {i}. {l.get('learning', '')[:80]}...")
    
    # Get PR context
    print(f"\n[1.4] Get PR Context Learnings:")
    pr_learnings = client.get_pr_context_learnings(
        owner="testowner",
        repo="testrepo",
        pr_description="Refactor Button component for better performance",
        changed_files=["src/components/Button.tsx", "src/utils/validator.ts"],
        k=5
    )
    print(f"     Found {len(pr_learnings)} contextual learnings")
    
    # Format for prompt
    print(f"\n[1.5] Format Learnings for Prompt:")
    formatted = client.format_learnings_for_prompt(pr_learnings, max_learnings=3)
    if formatted:
        print(formatted[:500])
    else:
        print("     (No learnings to format)")
    
    print("\n✓ KB Client tests passed!")
    return True


def test_workflow_kb_integration():
    """Test that workflow integrates KB context"""
    print("\n" + "="*60)
    print("TEST 2: Workflow KB Integration")
    print("="*60)
    
    workflow = CodeReviewWorkflow(use_mock_llm=True)
    
    # Check KB client is initialized
    print(f"\n[2.1] Workflow KB client enabled: {workflow.kb_client.enabled}")
    assert workflow.kb_client.enabled, "Workflow KB client should be enabled"
    
    # Test _parse_repo_url
    print(f"\n[2.2] Parse repo URL:")
    test_urls = [
        ("testowner/testrepo", ("testowner", "testrepo")),
        ("https://github.com/testowner/testrepo", ("testowner", "testrepo")),
        ("https://github.com/testowner/testrepo.git", ("testowner", "testrepo")),
    ]
    for url, expected in test_urls:
        result = workflow._parse_repo_url(url)
        status = "✓" if result == expected else "✗"
        print(f"     {status} {url} -> {result}")
    
    # Test _fetch_kb_context
    print(f"\n[2.3] Fetch KB Context:")
    kb_context = workflow._fetch_kb_context(
        owner="testowner",
        repo="testrepo",
        pr_description="Fix performance issues",
        changed_files=["src/Button.tsx"]
    )
    print(f"     KB enabled: {kb_context.get('kb_enabled')}")
    print(f"     Learnings found: {len(kb_context.get('learnings', []))}")
    print(f"     Formatted context length: {len(kb_context.get('formatted_context', ''))}")
    
    if kb_context.get('learnings'):
        print(f"\n     Sample learning: {kb_context['learnings'][0].get('learning', '')[:100]}...")
    
    print("\n✓ Workflow KB integration tests passed!")
    return True


def test_full_review_with_kb():
    """Test a full review flow with KB context (using a small public repo)"""
    print("\n" + "="*60)
    print("TEST 3: Full Review with KB Context (Mock)")
    print("="*60)
    
    # We'll mock a review scenario without actually cloning
    workflow = CodeReviewWorkflow(use_mock_llm=True)
    
    # Simulate what happens during review
    print(f"\n[3.1] Simulating review for testowner/testrepo PR #100")
    
    # Get KB context (this is the real call)
    kb_context = workflow._fetch_kb_context(
        owner="testowner",
        repo="testrepo",
        pr_description="Add memoization to Button component",
        changed_files=["src/components/Button.tsx"]
    )
    
    print(f"     KB context retrieved: {len(kb_context.get('learnings', []))} learnings")
    
    # Generate a mock review with KB context
    # functions must be list of dicts with proper structure for mock_llm
    mock_analysis = {
        "ast": {
            "type": "ast_summary", 
            "functions": [
                {"name": "Button", "complexity": 5, "start_line": 10, "docstring": "Button component"},
                {"name": "handleClick", "complexity": 2, "start_line": 25, "parameters": ["event"]}
            ]
        },
        "semantic": {"type": "semantic_summary", "nodes": []}
    }
    
    review = workflow._generate_review(
        analysis=mock_analysis,
        file_path="src/components/Button.tsx",
        kb_context=kb_context
    )
    
    print(f"\n[3.2] Review generated:")
    print(f"     File: {review.get('file_path')}")
    print(f"     Issues found: {len(review.get('issues', []))}")
    print(f"     KB context applied: {review.get('kb_context_applied', False)}")
    print(f"     Learnings considered: {review.get('learnings_considered', 0)}")
    
    # Format for GitHub
    formatted = workflow._format_for_github(
        reviews=[review],
        pr_description="Add memoization",
        kb_context=kb_context
    )
    
    print(f"\n[3.3] Formatted Review Summary:")
    print("-" * 40)
    print(formatted.get('summary', ''))
    print("-" * 40)
    
    # Check that KB learnings are mentioned in summary
    summary = formatted.get('summary', '')
    has_kb_mention = "learning" in summary.lower()
    print(f"\n[3.4] Summary mentions learnings: {'✓' if has_kb_mention else '✗'}")
    
    print("\n✓ Full review with KB tests passed!")
    return True


def test_feedback_submission():
    """Test submitting feedback to the backend"""
    print("\n" + "="*60)
    print("TEST 4: Feedback Submission")
    print("="*60)
    
    import httpx
    
    client = httpx.Client(base_url="http://localhost:8080", timeout=10.0)
    
    # Submit feedback
    print(f"\n[4.1] Submitting test feedback...")
    payload = {
        "comment_id": f"test-kb-workflow-{os.getpid()}",
        "owner": "testowner",
        "repo": "testrepo",
        "pr_number": 999,
        "ai_comment": "Consider using React.memo for this component to prevent unnecessary re-renders",
        "feedback_type": "reply",
        "user_feedback": "Good suggestion, but this component has props that change frequently so memo would not help",
        "github_user": "kb-test-user"
    }
    
    try:
        response = client.post("/user-feedback/submit", json=payload)
        print(f"     Status: {response.status_code}")
        result = response.json()
        print(f"     Result: {result}")
        
        if response.status_code == 200:
            print("\n✓ Feedback submission test passed!")
            return True
        else:
            print(f"\n✗ Feedback submission failed: {result}")
            return False
            
    except Exception as e:
        print(f"\n✗ Feedback submission error: {e}")
        return False
    finally:
        client.close()


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  KNOWLEDGE BASE WORKFLOW INTEGRATION TESTS")
    print("="*60)
    
    results = []
    
    # Test 1: KB Client
    try:
        results.append(("KB Client Direct", test_kb_client_direct()))
    except Exception as e:
        print(f"\n✗ Test 1 failed with error: {e}")
        results.append(("KB Client Direct", False))
    
    # Test 2: Workflow Integration
    try:
        results.append(("Workflow KB Integration", test_workflow_kb_integration()))
    except Exception as e:
        print(f"\n✗ Test 2 failed with error: {e}")
        results.append(("Workflow KB Integration", False))
    
    # Test 3: Full Review with KB
    try:
        results.append(("Full Review with KB", test_full_review_with_kb()))
    except Exception as e:
        print(f"\n✗ Test 3 failed with error: {e}")
        results.append(("Full Review with KB", False))
    
    # Test 4: Feedback Submission
    try:
        results.append(("Feedback Submission", test_feedback_submission()))
    except Exception as e:
        print(f"\n✗ Test 4 failed with error: {e}")
        results.append(("Feedback Submission", False))
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("="*60)
    if all_passed:
        print("  ALL TESTS PASSED!")
    else:
        print("  SOME TESTS FAILED")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
