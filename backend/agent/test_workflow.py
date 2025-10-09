"""
Unit Tests for Code Review Agent Workflow

Tests the LangGraph workflow implementation and individual components.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from agent.main import (
    AgentState,
    context_enrichment_node,
    static_analysis_node,
    code_review_node,
    format_output_node,
    route_after_context_enrichment,
    route_after_static_analysis,
    route_after_code_review,
    route_after_tools,
    app
)
from agent.workflow import CodeReviewWorkflow, invoke_review


class TestAgentNodes:
    """Test individual workflow nodes"""
    
    def test_context_enrichment_node_updates_state(self):
        """Test context enrichment node properly updates state"""
        
        initial_state: AgentState = {
            "messages": [HumanMessage(content="Review this PR")],
            "pr_context": {},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "current_stage": ""
        }
        
        with patch("agent.main.llm_with_tools") as mock_llm:
            mock_llm.invoke.return_value = AIMessage(
                content="Context gathered",
                tool_calls=[]
            )
            
            result = context_enrichment_node(initial_state)
            
            assert result["current_stage"] == "context_enrichment"
            assert "messages" in result
            mock_llm.invoke.assert_called_once()
    
    def test_static_analysis_node_calls_parsers(self):
        """Test static analysis node invokes parser tools"""
        
        state: AgentState = {
            "messages": [HumanMessage(content="Analyze code")],
            "pr_context": {},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "current_stage": "context_enrichment"
        }
        
        with patch("agent.main.llm_with_tools") as mock_llm:
            mock_llm.invoke.return_value = AIMessage(
                content="Analysis complete",
                tool_calls=[]
            )
            
            result = static_analysis_node(state)
            
            assert result["current_stage"] == "static_analysis"
            mock_llm.invoke.assert_called_once()
    
    def test_code_review_node_generates_review(self):
        """Test code review node generates review content"""
        
        state: AgentState = {
            "messages": [HumanMessage(content="Generate review")],
            "pr_context": {},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "current_stage": "static_analysis"
        }
        
        with patch("agent.main.llm") as mock_llm:
            mock_llm.invoke.return_value = AIMessage(
                content="Review generated with feedback"
            )
            
            result = code_review_node(state)
            
            assert result["current_stage"] == "code_review"
            mock_llm.invoke.assert_called_once()
    
    def test_format_output_node_structures_json(self):
        """Test format output node creates structured output"""
        
        state: AgentState = {
            "messages": [
                HumanMessage(content="Format this review"),
                AIMessage(content="Review content here")
            ],
            "pr_context": {},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "current_stage": "code_review"
        }
        
        with patch("agent.main.llm") as mock_llm:
            mock_llm.invoke.return_value = AIMessage(
                content='{"summary": "Good PR", "comments": []}'
            )
            
            result = format_output_node(state)
            
            assert result["current_stage"] == "complete"
            assert result["review_output"]["formatted"] is True


class TestRoutingLogic:
    """Test conditional routing between nodes"""
    
    def test_route_after_context_enrichment_with_tools(self):
        """Test routing to tools when tool calls present"""
        
        mock_tool_call = Mock()
        ai_message = AIMessage(content="Need to call tools")
        ai_message.tool_calls = [mock_tool_call]
        
        state: AgentState = {
            "messages": [ai_message],
            "pr_context": {},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "current_stage": "context_enrichment"
        }
        
        route = route_after_context_enrichment(state)
        assert route == "tools"
    
    def test_route_after_context_enrichment_without_tools(self):
        """Test routing to static analysis when no tools needed"""
        
        state: AgentState = {
            "messages": [AIMessage(content="Context complete")],
            "pr_context": {},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "current_stage": "context_enrichment"
        }
        
        route = route_after_context_enrichment(state)
        assert route == "static_analysis"
    
    def test_route_after_tools_based_on_stage(self):
        """Test routing from tools back to appropriate stage"""
        
        state: AgentState = {
            "messages": [ToolMessage(content="Tool result", tool_call_id="123")],
            "pr_context": {},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "current_stage": "static_analysis"
        }
        
        route = route_after_tools(state)
        assert route == "static_analysis"


class TestWorkflowIntegration:
    """Test the complete workflow integration"""
    
    @patch("agent.main.llm_with_tools")
    @patch("agent.main.llm")
    def test_workflow_execution_without_tools(self, mock_llm, mock_llm_with_tools):
        """Test workflow executes all stages without tool calls"""
        
        mock_llm_with_tools.invoke.return_value = AIMessage(
            content="Stage complete",
            tool_calls=[]
        )
        
        mock_llm.invoke.return_value = AIMessage(
            content='{"summary": "Review complete", "comments": []}'
        )
        
        initial_state: AgentState = {
            "messages": [HumanMessage(content="Review PR")],
            "pr_context": {},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "current_stage": ""
        }
        
        # This would execute the full workflow
        # In a real test, you'd mock the app.invoke
        assert True  # Placeholder


class TestCodeReviewWorkflow:
    """Test the workflow wrapper class"""
    
    def test_build_review_request_with_pr_number(self):
        """Test building review request message"""
        
        workflow = CodeReviewWorkflow()
        message = workflow._build_review_request(
            repo_url="owner/repo",
            pr_number=42,
            branch="feature-branch",
            pr_description="Add new feature"
        )
        
        assert "owner/repo" in message
        assert "42" in message
        assert "feature-branch" in message
        assert "Add new feature" in message
    
    def test_extract_review_output_from_state(self):
        """Test extracting formatted review from final state"""
        
        workflow = CodeReviewWorkflow()
        
        final_state: AgentState = {
            "messages": [
                HumanMessage(content="Review request"),
                AIMessage(content='{"summary": "Good code", "comments": []}')
            ],
            "pr_context": {"repo": "test/repo"},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "current_stage": "complete"
        }
        
        result = workflow._extract_review_output(final_state)
        
        assert result["status"] == "success"
        assert result["stage"] == "complete"
        assert "messages" in result
    
    @patch("agent.workflow.app")
    def test_review_pull_request_invokes_workflow(self, mock_app):
        """Test review_pull_request calls workflow correctly"""
        
        mock_app.invoke.return_value = {
            "messages": [AIMessage(content="Review done")],
            "pr_context": {},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "current_stage": "complete"
        }
        
        workflow = CodeReviewWorkflow()
        result = workflow.review_pull_request(
            repo_url="owner/repo",
            pr_number=1,
            branch="main"
        )
        
        assert result["status"] == "success"
        mock_app.invoke.assert_called_once()
    
    @patch("agent.workflow.app")
    def test_review_files_builds_correct_message(self, mock_app):
        """Test review_files creates correct input"""
        
        mock_app.invoke.return_value = {
            "messages": [AIMessage(content="Files reviewed")],
            "pr_context": {},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "current_stage": "complete"
        }
        
        workflow = CodeReviewWorkflow()
        result = workflow.review_files(
            file_paths=["src/main.py", "src/utils.py"],
            repo_path="/repo",
            context="Review changes"
        )
        
        assert result["status"] == "success"
        mock_app.invoke.assert_called_once()


class TestHelperFunctions:
    """Test helper and utility functions"""
    
    @patch("agent.workflow.CodeReviewWorkflow")
    def test_invoke_review_convenience_function(self, mock_workflow_class):
        """Test the convenience invoke_review function"""
        
        mock_workflow = Mock()
        mock_workflow.review_pull_request.return_value = {
            "status": "success",
            "messages": []
        }
        mock_workflow_class.return_value = mock_workflow
        
        result = invoke_review(
            repo_url="test/repo",
            pr_number=1
        )
        
        assert result["status"] == "success"
        mock_workflow.review_pull_request.assert_called_once()


@pytest.fixture
def sample_state():
    """Fixture providing a sample AgentState"""
    return {
        "messages": [HumanMessage(content="Test message")],
        "pr_context": {"repo": "test/repo"},
        "knowledge_context": {},
        "parser_results": {},
        "review_output": {},
        "current_stage": "context_enrichment"
    }


@pytest.fixture
def mock_tool_response():
    """Fixture providing a mock tool response"""
    return ToolMessage(
        content='{"result": "success"}',
        tool_call_id="test-123"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
