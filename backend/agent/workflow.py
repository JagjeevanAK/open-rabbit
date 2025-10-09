"""
Code Review Agent Workflow Executor

This module provides utilities to execute the LangGraph workflow for code reviews.
"""

from typing import Dict, Any, Optional, List
from langchain_core.messages import HumanMessage
from agent.main import app, AgentState
import json


class CodeReviewWorkflow:
    """Wrapper for executing the code review workflow"""
    
    def __init__(self):
        self.app = app
    
    def review_pull_request(
        self,
        repo_url: str,
        pr_number: Optional[int] = None,
        branch: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        pr_description: Optional[str] = None,
        generate_tests: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a complete code review workflow for a pull request.
        
        Args:
            repo_url: GitHub repository URL (e.g., 'username/repo' or full URL)
            pr_number: Pull request number (if reviewing specific PR)
            branch: Branch name to review
            changed_files: List of changed files (if known)
            pr_description: Description of the pull request
            generate_tests: Whether to generate unit tests for changed files
            
        Returns:
            Dictionary containing the review results
        """
        
        input_message = self._build_review_request(
            repo_url=repo_url,
            pr_number=pr_number,
            branch=branch,
            changed_files=changed_files,
            pr_description=pr_description,
            generate_tests=generate_tests
        )
        
        initial_state: AgentState = {
            "messages": [HumanMessage(content=input_message)],
            "pr_context": {},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "unit_tests": {},
            "current_stage": "context_enrichment",
            "generate_tests": generate_tests
        }
        
        final_state = self.app.invoke(initial_state)
        
        return self._extract_review_output(final_state)
    
    def review_files(
        self,
        file_paths: List[str],
        repo_path: str,
        context: Optional[str] = None,
        generate_tests: bool = False
    ) -> Dict[str, Any]:
        """
        Review specific files without a PR context.
        
        Args:
            file_paths: List of file paths to review
            repo_path: Path to the repository
            context: Additional context about the review
            generate_tests: Whether to generate unit tests
            
        Returns:
            Dictionary containing the review results
        """
        
        files_str = "\n".join([f"- {fp}" for fp in file_paths])
        
        input_message = f"""Please review the following files:

Repository: {repo_path}

Files to review:
{files_str}

{f'Context: {context}' if context else ''}

Perform a comprehensive code review including:
1. Gather relevant learnings from knowledge base
2. Perform static analysis (AST, CFG, PDG)
3. Provide detailed feedback on code quality, bugs, and improvements
{f'4. Generate unit tests for the files' if generate_tests else ''}
"""
        
        initial_state: AgentState = {
            "messages": [HumanMessage(content=input_message)],
            "pr_context": {"repo_path": repo_path, "files": file_paths},
            "knowledge_context": {},
            "parser_results": {},
            "review_output": {},
            "unit_tests": {},
            "current_stage": "context_enrichment",
            "generate_tests": generate_tests
        }
        
        final_state = self.app.invoke(initial_state)
        
        return self._extract_review_output(final_state)
    
    def _build_review_request(
        self,
        repo_url: str,
        pr_number: Optional[int] = None,
        branch: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        pr_description: Optional[str] = None,
        generate_tests: bool = False
    ) -> str:
        """Build the review request message"""
        
        message_parts = [
            f"Please perform a comprehensive code review for:",
            f"Repository: {repo_url}"
        ]
        
        if pr_number:
            message_parts.append(f"Pull Request: #{pr_number}")
        
        if branch:
            message_parts.append(f"Branch: {branch}")
        
        if pr_description:
            message_parts.append(f"\nPR Description:\n{pr_description}")
        
        if changed_files:
            files_list = "\n".join([f"  - {f}" for f in changed_files])
            message_parts.append(f"\nChanged files:\n{files_list}")
        
        review_steps = [
            "1. **Context Enrichment**: Clone the repository, gather knowledge base learnings, and read changed files",
            "2. **Static Analysis**: Analyze code using AST, CFG, and PDG parsers",
            "3. **Code Review**: Generate comprehensive review based on all context"
        ]
        
        if generate_tests:
            review_steps.append("4. **Unit Test Generation**: Generate comprehensive unit tests for changed files")
            review_steps.append("5. **Format Output**: Return structured JSON review comments")
        else:
            review_steps.append("4. **Format Output**: Return structured JSON review comments")
        
        message_parts.append(f"\nReview Process:\n" + "\n".join(review_steps))
        message_parts.append("\nStart by cloning the repository and gathering context.")
        
        return "\n".join(message_parts)
    
    def _extract_review_output(self, final_state: AgentState) -> Dict[str, Any]:
        """Extract and format the review output from final state"""
        
        messages = final_state.get("messages", [])
        
        review_output = {
            "status": "success",
            "stage": final_state.get("current_stage", "unknown"),
            "pr_context": final_state.get("pr_context", {}),
            "knowledge_context": final_state.get("knowledge_context", {}),
            "parser_results": final_state.get("parser_results", {}),
            "unit_tests": final_state.get("unit_tests", {}),
            "messages": []
        }
        
        for msg in messages:
            if hasattr(msg, "content"):
                content = msg.content
                
                if isinstance(content, str) and content.strip():
                    try:
                        parsed = json.loads(content)
                        if "comments" in parsed or "summary" in parsed:
                            review_output["formatted_review"] = parsed
                    except (json.JSONDecodeError, ValueError):
                        pass
                    
                    review_output["messages"].append({
                        "type": msg.__class__.__name__,
                        "content": content
                    })
        
        if not review_output.get("formatted_review") and messages:
            last_message = messages[-1]
            if hasattr(last_message, "content"):
                review_output["raw_review"] = last_message.content
        
        return review_output


def invoke_review(
    repo_url: str,
    pr_number: Optional[int] = None,
    branch: Optional[str] = None,
    changed_files: Optional[List[str]] = None,
    pr_description: Optional[str] = None,
    generate_tests: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to invoke a code review.
    
    Args:
        repo_url: GitHub repository URL
        pr_number: Pull request number
        branch: Branch name
        changed_files: List of changed files
        pr_description: PR description
        generate_tests: Whether to generate unit tests
        
    Returns:
        Review results dictionary
    """
    workflow = CodeReviewWorkflow()
    return workflow.review_pull_request(
        repo_url=repo_url,
        pr_number=pr_number,
        branch=branch,
        changed_files=changed_files,
        pr_description=pr_description,
        generate_tests=generate_tests
    )
