#!/usr/bin/env python3
"""
Integration Tests for the Multi-Agent Code Review System

Tests the full SupervisorAgent pipeline with mock mode.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from agent import (
    SupervisorAgent,
    ReviewRequest,
    SupervisorConfig,
    SupervisorOutput,
    FileChange,
    AgentStatus,
    Severity,
    IssueCategory,
)
from agent.supervisor import Reducer, KBFilter
from agent.subagents import ParserAgent, ReviewAgent


def test_supervisor_with_mock():
    """Test the full supervisor pipeline with mock LLM."""
    print("\n" + "="*60)
    print("Test: Supervisor with Mock LLM")
    print("="*60)
    
    # Create a temp directory with test files
    temp_dir = tempfile.mkdtemp(prefix="open-rabbit-test-")
    
    try:
        # Create test Python file with some issues
        test_file = Path(temp_dir) / "test_module.py"
        test_file.write_text('''
import os
import sys  # unused import

def calculate_total(items):
    """Calculate total price."""
    total = 0
    for item in items:
        total += item.price
    return total

def risky_function(user_input):
    # SQL injection risk
    query = f"SELECT * FROM users WHERE id = {user_input}"
    return query

def complex_function(a, b, c, d, e, f):
    """A complex function with high cyclomatic complexity."""
    result = 0
    if a > 0:
        if b > 0:
            if c > 0:
                result = a + b + c
            else:
                result = a + b
        else:
            if d > 0:
                result = a + d
            else:
                result = a
    else:
        if e > 0:
            if f > 0:
                result = e + f
            else:
                result = e
        else:
            result = 0
    return result

unused_variable = "this is never used"
''')
        
        # Create config with mock mode
        config = SupervisorConfig(
            use_mock=True,
            kb_enabled=False,
            enable_checkpointing=True,
            max_files=10,
        )
        
        # Create review request
        request = ReviewRequest(
            owner="test-org",
            repo="test-repo",
            pr_number=123,
            branch="feature/test",
            changed_files=[
                FileChange(
                    path="test_module.py",
                    status="modified",
                    additions=30,
                    deletions=5,
                    patch="@@ -1,5 +1,30 @@\n+import os",
                )
            ],
            pr_title="Test PR: Add calculation functions",
            pr_description="This PR adds some calculation utilities.",
            repo_path=temp_dir,
        )
        
        # Create and run supervisor
        supervisor = SupervisorAgent(config=config)
        print(f"Running supervisor on {request.owner}/{request.repo}...")
        
        output, checkpoint = supervisor.run(request)
        
        # Verify output
        assert output.status == AgentStatus.SUCCESS, f"Expected SUCCESS, got {output.status}"
        assert output.files_analyzed == 1, f"Expected 1 file, got {output.files_analyzed}"
        
        print(f"\n✅ Status: {output.status.value}")
        print(f"📁 Files analyzed: {output.files_analyzed}")
        print(f"🔍 Issues found: {len(output.issues)}")
        print(f"⏱️ Duration: {output.duration_seconds:.2f}s")
        
        # Print issues
        if output.issues:
            print(f"\n📋 Issues:")
            for i, issue in enumerate(output.issues, 1):
                print(f"  {i}. [{issue.severity.value.upper()}] {issue.title}")
                print(f"     File: {issue.file_path}:{issue.line_start}")
                print(f"     Category: {issue.category.value}")
        
        # Print summary
        print(f"\n📝 Summary:\n{output.summary}")
        
        # Verify parser found security issues
        if output.parser_summary:
            print(f"\n🔬 Parser Summary:")
            for key, value in output.parser_summary.items():
                print(f"  {key}: {value}")
        
        # Verify checkpoint
        assert checkpoint is not None
        assert checkpoint.status == AgentStatus.SUCCESS
        print(f"\n✅ Checkpoint: {checkpoint.agent_name} - {checkpoint.status.value}")
        
        print("\n" + "="*60)
        print("TEST PASSED: Supervisor with Mock LLM")
        print("="*60)
        return True
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_parser_agent_standalone():
    """Test the Parser Agent in isolation."""
    print("\n" + "="*60)
    print("Test: Parser Agent Standalone")
    print("="*60)
    
    temp_dir = tempfile.mkdtemp(prefix="open-rabbit-parser-test-")
    
    try:
        # Create test file with security issue
        test_file = Path(temp_dir) / "vulnerable.py"
        test_file.write_text('''
import os

def run_command(user_input):
    # Command injection vulnerability
    os.system(f"echo {user_input}")
    
def get_secret():
    api_key = "sk-1234567890abcdef"  # Hardcoded secret
    return api_key
''')
        
        from agent.schemas.parser_output import ParserInput
        
        parser = ParserAgent(max_workers=1)
        
        input_data = ParserInput(
            changed_files=[
                FileChange(path="vulnerable.py", status="modified")
            ],
            repo_path=temp_dir,
            enable_security_scan=True,
            enable_dead_code_detection=True,
        )
        
        output, checkpoint = parser.run(input_data)
        
        print(f"✅ Parser Status: {checkpoint.status.value}")
        print(f"📁 Files analyzed: {output.total_files}")
        print(f"🔒 Security issues: {output.total_security_issues}")
        print(f"🗑️ Dead code: {output.total_dead_code}")
        
        # Print security issues
        for fa in output.files:
            for si in fa.security_issues:
                print(f"  🔴 [{si.severity.value}] {si.type.value} at line {si.line}")
                print(f"     {si.description[:80]}...")
        
        assert output.total_files == 1
        assert output.total_security_issues >= 1, "Should find at least one security issue"
        
        print("\n" + "="*60)
        print("TEST PASSED: Parser Agent Standalone")
        print("="*60)
        return True
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_review_agent_mock():
    """Test the Review Agent with mock mode."""
    print("\n" + "="*60)
    print("Test: Review Agent with Mock")
    print("="*60)
    
    temp_dir = tempfile.mkdtemp(prefix="open-rabbit-review-test-")
    
    try:
        test_file = Path(temp_dir) / "sample.py"
        test_file.write_text('''
def add(a, b):
    return a + b
''')
        
        from agent.schemas.review_output import ReviewInput
        from agent.schemas.common import PRContext
        
        reviewer = ReviewAgent(use_mock=True)
        
        input_data = ReviewInput(
            owner="test",
            repo="test-repo",
            changed_files=[
                FileChange(path="sample.py", status="modified")
            ],
            repo_path=temp_dir,
            pr_context=PRContext(
                title="Test PR",
                description="A test pull request",
            ),
        )
        
        output, checkpoint = reviewer.run(input_data)
        
        print(f"✅ Review Status: {checkpoint.status.value}")
        print(f"📁 Files reviewed: {output.files_reviewed}")
        print(f"🔍 Issues found: {len(output.issues)}")
        
        assert checkpoint.status == AgentStatus.SUCCESS
        
        print("\n" + "="*60)
        print("TEST PASSED: Review Agent with Mock")
        print("="*60)
        return True
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_reducer():
    """Test the Reducer component."""
    print("\n" + "="*60)
    print("Test: Reducer")
    print("="*60)
    
    from agent.schemas.common import ReviewIssue
    
    # Create some overlapping issues
    parser_issues = [
        ReviewIssue(
            file_path="test.py",
            line_start=10,
            severity=Severity.HIGH,
            category=IssueCategory.SECURITY,
            title="SQL Injection",
            message="Potential SQL injection vulnerability",
            source="parser",
            confidence=0.9,
        ),
        ReviewIssue(
            file_path="test.py",
            line_start=20,
            severity=Severity.MEDIUM,
            category=IssueCategory.COMPLEXITY,
            title="High Complexity",
            message="Function has high cyclomatic complexity",
            source="parser",
            confidence=0.95,
        ),
    ]
    
    review_issues = [
        ReviewIssue(
            file_path="test.py",
            line_start=10,  # Same line as parser issue
            severity=Severity.CRITICAL,  # Higher severity
            category=IssueCategory.SECURITY,
            title="SQL Injection Risk",
            message="User input directly used in SQL query",
            source="review",
            confidence=0.85,
        ),
        ReviewIssue(
            file_path="test.py",
            line_start=30,
            severity=Severity.LOW,
            category=IssueCategory.STYLE,
            title="Missing docstring",
            message="Function lacks documentation",
            source="review",
            confidence=0.7,
        ),
    ]
    
    reducer = Reducer()
    reduced = reducer.reduce(parser_issues, review_issues)
    
    print(f"📥 Input: {len(parser_issues)} parser + {len(review_issues)} review = {len(parser_issues) + len(review_issues)} total")
    print(f"📤 Output: {len(reduced)} reduced issues")
    
    for issue in reduced:
        print(f"  - [{issue.severity.value}] {issue.title} (source: {issue.source})")
    
    # Should have merged the SQL injection issues
    assert len(reduced) <= len(parser_issues) + len(review_issues)
    
    print("\n" + "="*60)
    print("TEST PASSED: Reducer")
    print("="*60)
    return True


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("🧪 OPEN RABBIT - MULTI-AGENT INTEGRATION TESTS")
    print("="*60)
    
    tests = [
        ("Parser Agent Standalone", test_parser_agent_standalone),
        ("Review Agent Mock", test_review_agent_mock),
        ("Reducer", test_reducer),
        ("Supervisor with Mock", test_supervisor_with_mock),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
                print(f"\n❌ FAILED: {name}")
        except Exception as e:
            failed += 1
            print(f"\n❌ ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print(f"🏁 RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
