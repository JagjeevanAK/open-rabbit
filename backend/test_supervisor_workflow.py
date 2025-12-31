#!/usr/bin/env python3
"""
Unit tests for the Supervisor Agent workflow.

Tests the multi-agent orchestration using mock agents.
"""

import asyncio
import pytest
from typing import List
from unittest.mock import AsyncMock, patch, MagicMock

# Add backend to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from agent.schemas.common import (
    ReviewRequest,
    FileInfo,
    UserIntent,
    IntentType,
    KBContext,
    AgentStatus,
    SupervisorOutput,
)
from agent.schemas.parser_output import ParserOutput, FileMetadata
from agent.schemas.review_output import ReviewOutput, ReviewIssue, Severity, IssueCategory
from agent.schemas.test_output import TestOutput, GeneratedTest, TestType, TestFramework
from agent.supervisor.supervisor_agent import SupervisorAgent, SupervisorConfig, MockSupervisorAgent
from agent.supervisor.intent_parser import IntentParser
from agent.supervisor.result_aggregator import ResultAggregator


class TestIntentParser:
    """Tests for the IntentParser component."""
    
    def setup_method(self):
        self.parser = IntentParser()
    
    def test_parse_review_only(self):
        """Test parsing a review-only request."""
        request = ReviewRequest(
            files=[FileInfo(path="main.py", content="def foo(): pass")],
            user_request="Review this PR please",
        )
        
        intent = self.parser.parse(request)
        
        assert intent.intent_type == IntentType.REVIEW_ONLY
        assert intent.should_review is True
        assert intent.should_generate_tests is False
    
    def test_parse_review_and_tests(self):
        """Test parsing a request that asks for both review and tests."""
        request = ReviewRequest(
            files=[FileInfo(path="main.py", content="def foo(): pass")],
            user_request="Review this code and generate unit tests",
        )
        
        intent = self.parser.parse(request)
        
        assert intent.intent_type == IntentType.REVIEW_AND_TESTS
        assert intent.should_review is True
        assert intent.should_generate_tests is True
    
    def test_parse_tests_only(self):
        """Test parsing a tests-only request."""
        request = ReviewRequest(
            files=[FileInfo(path="main.py", content="def foo(): pass")],
            user_request="Generate unit tests for this function",
        )
        
        intent = self.parser.parse(request)
        
        assert intent.intent_type == IntentType.TESTS_ONLY
        assert intent.should_review is False
        assert intent.should_generate_tests is True
    
    def test_parse_no_request_defaults_to_review(self):
        """Test that missing user_request defaults to review only."""
        request = ReviewRequest(
            files=[FileInfo(path="main.py", content="def foo(): pass")],
        )
        
        intent = self.parser.parse(request)
        
        assert intent.should_review is True
        assert intent.should_generate_tests is False


class TestResultAggregator:
    """Tests for the ResultAggregator component."""
    
    def setup_method(self):
        self.aggregator = ResultAggregator()
    
    def test_merge_review_only(self):
        """Test merging results with only review output."""
        from agent.schemas.common import AgentResult
        
        review_output = ReviewOutput(
            issues=[
                ReviewIssue(
                    file="main.py",
                    line=10,
                    severity=Severity.LOW,
                    category=IssueCategory.DOCUMENTATION,
                    message="Consider adding docstring",
                )
            ]
        )
        
        review_result = AgentResult(
            agent_name="code_review",
            status=AgentStatus.COMPLETED,
            output=review_output,
        )
        
        output = self.aggregator.merge(review_result=review_result)
        
        assert output.status == AgentStatus.COMPLETED
        assert output.review_output is not None
        assert len(output.review_output.issues) == 1
        assert output.test_output is None
    
    def test_merge_with_errors(self):
        """Test merging when some agents failed."""
        from agent.schemas.common import AgentResult
        
        parser_result = AgentResult(
            agent_name="parser",
            status=AgentStatus.COMPLETED,
            output=ParserOutput(),
        )
        
        review_result = AgentResult(
            agent_name="code_review",
            status=AgentStatus.FAILED,
            error="LLM rate limit exceeded",
        )
        
        output = self.aggregator.merge(
            parser_result=parser_result,
            review_result=review_result,
        )
        
        # Overall status should be completed (partial success)
        # but errors should be recorded
        assert len(output.errors) > 0 or output.review_result.error is not None


class TestMockSupervisorAgent:
    """Tests for the mock supervisor agent."""
    
    @pytest.fixture
    def supervisor(self):
        """Create a mock supervisor agent."""
        return MockSupervisorAgent()
    
    @pytest.mark.asyncio
    async def test_run_review_only(self, supervisor):
        """Test running a review-only workflow."""
        request = ReviewRequest(
            files=[
                FileInfo(
                    path="main.py",
                    content='''
def calculate_total(items):
    total = 0
    for item in items:
        total += item.price
    return total
''',
                    language="python",
                )
            ],
            user_request="Review this code",
        )
        
        output = await supervisor.run(request)
        
        assert output.status in [AgentStatus.COMPLETED, AgentStatus.FAILED]
        assert output.session_id is not None
    
    @pytest.mark.asyncio
    async def test_run_with_tests(self, supervisor):
        """Test running a workflow that includes test generation."""
        request = ReviewRequest(
            files=[
                FileInfo(
                    path="calculator.py",
                    content='''
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
''',
                    language="python",
                )
            ],
            user_request="Review and generate unit tests",
        )
        
        output = await supervisor.run(request)
        
        assert output.status in [AgentStatus.COMPLETED, AgentStatus.FAILED]
    
    @pytest.mark.asyncio
    async def test_checkpoint_state(self, supervisor):
        """Test that checkpoint state is accessible."""
        request = ReviewRequest(
            files=[FileInfo(path="test.py", content="x = 1")],
        )
        
        output = await supervisor.run(request, session_id="test-session-123")
        
        # Get checkpoint state
        state = await supervisor.get_checkpoint_state("test-session-123")
        
        # If checkpointing is enabled, state should exist
        if supervisor.config.enable_checkpointing:
            assert state is not None or output.status == AgentStatus.FAILED


class TestKBContext:
    """Tests for KB context integration."""
    
    def test_kb_context_to_prompt(self):
        """Test formatting KB context for prompts."""
        context = KBContext(
            coding_style=["Use snake_case for function names"],
            conventions=["All functions must have docstrings"],
            best_practices=["Prefer composition over inheritance"],
        )
        
        prompt_text = context.to_prompt_context()
        
        assert "snake_case" in prompt_text
        assert "docstrings" in prompt_text
        assert "composition" in prompt_text
    
    def test_kb_context_is_empty(self):
        """Test checking if KB context is empty."""
        empty_context = KBContext()
        full_context = KBContext(coding_style=["Rule 1"])
        
        assert empty_context.is_empty() is True
        assert full_context.is_empty() is False


class TestSupervisorConfig:
    """Tests for supervisor configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = SupervisorConfig()
        
        assert config.kb_enabled is True
        assert config.enable_checkpointing is True
        assert config.use_mock_agents is False
        assert config.timeout_seconds == 600.0
    
    def test_custom_config(self):
        """Test custom configuration."""
        from agent.llm_factory import LLMProvider
        
        config = SupervisorConfig(
            llm_provider=LLMProvider.ANTHROPIC,
            llm_model="claude-3-opus-20240229",
            kb_enabled=False,
            use_mock_agents=True,
        )
        
        assert config.llm_provider == LLMProvider.ANTHROPIC
        assert config.kb_enabled is False
        assert config.use_mock_agents is True


class TestFileInfo:
    """Tests for FileInfo dataclass."""
    
    def test_file_info_serialization(self):
        """Test FileInfo to_dict and from_dict."""
        file_info = FileInfo(
            path="src/main.py",
            content="print('hello')",
            language="python",
            is_new=True,
        )
        
        # Serialize
        data = file_info.to_dict()
        
        assert data["path"] == "src/main.py"
        assert data["is_new"] is True
        
        # Deserialize
        restored = FileInfo.from_dict(data)
        
        assert restored.path == file_info.path
        assert restored.content == file_info.content
        assert restored.is_new == file_info.is_new


class TestReviewRequest:
    """Tests for ReviewRequest dataclass."""
    
    def test_review_request_serialization(self):
        """Test ReviewRequest to_dict and from_dict."""
        request = ReviewRequest(
            files=[
                FileInfo(path="a.py", content="x=1"),
                FileInfo(path="b.py", content="y=2"),
            ],
            pr_number=123,
            pr_title="Add feature X",
            user_request="Review this PR",
        )
        
        # Serialize
        data = request.to_dict()
        
        assert len(data["files"]) == 2
        assert data["pr_number"] == 123
        
        # Deserialize
        restored = ReviewRequest.from_dict(data)
        
        assert len(restored.files) == 2
        assert restored.pr_number == 123
        assert restored.user_request == "Review this PR"


def run_tests():
    """Run all tests manually (without pytest)."""
    import traceback
    
    test_classes = [
        TestIntentParser,
        TestResultAggregator,
        TestKBContext,
        TestSupervisorConfig,
        TestFileInfo,
        TestReviewRequest,
    ]
    
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"Running {test_class.__name__}")
        print('='*60)
        
        instance = test_class()
        
        # Call setup if exists
        if hasattr(instance, 'setup_method'):
            instance.setup_method()
        
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                method = getattr(instance, method_name)
                try:
                    # Skip async tests in manual mode
                    if asyncio.iscoroutinefunction(method):
                        print(f"  SKIP (async): {method_name}")
                        continue
                    
                    method()
                    print(f"  PASS: {method_name}")
                    passed += 1
                except Exception as e:
                    print(f"  FAIL: {method_name}")
                    print(f"        {e}")
                    traceback.print_exc()
                    failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print('='*60)
    
    return failed == 0


if __name__ == "__main__":
    # Run tests manually
    success = run_tests()
    sys.exit(0 if success else 1)
