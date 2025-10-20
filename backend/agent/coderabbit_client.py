"""
CodeRabbit Client - Easy interface for the CodeRabbit-like review agent

Usage:
    from agent.coderabbit_client import CodeRabbitReviewer
    
    reviewer = CodeRabbitReviewer()
    result = reviewer.review_pr(
        repo_url="owner/repo",
        pr_number=123,
        files=["file1.py", "file2.py"]
    )
"""

from typing import Dict, Any, Optional, List
from langchain_core.messages import HumanMessage
from agent.coderabbit_workflow import coderabbit_app, CodeRabbitAgentState


class CodeRabbitReviewer:
    """High-level interface for CodeRabbit-style code reviews"""
    
    def __init__(self):
        self.app = coderabbit_app
    
    def review_pr(
        self,
        repo_url: str,
        pr_number: Optional[int] = None,
        branch: Optional[str] = None,
        files: Optional[List[str]] = None,
        pr_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform a CodeRabbit-style review on a pull request.
        
        This will:
        1. Clone the repository
        2. For each file:
           a. Generate parser reports (AST, CFG, PDG, Semantic)
           b. Recursively analyze code + reports
           c. Find issues
           d. Validate against knowledge base
        3. Prepare PR comments
        4. Return structured review
        
        Args:
            repo_url: GitHub repository URL (e.g., 'owner/repo')
            pr_number: Pull request number
            branch: Branch name
            files: List of files to review
            pr_description: PR description
            
        Returns:
            Dictionary with review results
        """
        
        # Build the input message
        input_message = self._build_review_request(
            repo_url=repo_url,
            pr_number=pr_number,
            branch=branch,
            files=files,
            pr_description=pr_description
        )
        
        # Initialize state
        initial_state: CodeRabbitAgentState = {
            "messages": [HumanMessage(content=input_message)],
            "pr_context": {
                "repo_url": repo_url,
                "pr_number": pr_number,
                "branch": branch or "main"
            },
            "knowledge_context": {},
            "files_to_analyze": files or [],
            "current_file": files[0] if files else None,
            "file_analysis": {},
            "parser_reports": {},
            "issues_found": [],
            "validated_issues": [],
            "comments_to_post": [],
            "current_stage": "initialize",
            "iteration_count": 0,
            "max_iterations": 10
        }
        
        # Run the workflow
        final_state = self.app.invoke(initial_state)
        
        # Extract results
        return self._extract_results(final_state)
    
    def review_files(
        self,
        file_paths: List[str],
        repo_path: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Review specific files without a PR context.
        
        Args:
            file_paths: List of file paths to review
            repo_path: Path to the repository
            context: Additional context
            
        Returns:
            Dictionary with review results
        """
        
        input_message = f"""Please perform a CodeRabbit-style review of the following files:

Repository: {repo_path}

Files to review:
{chr(10).join([f"- {fp}" for fp in file_paths])}

{f'Context: {context}' if context else ''}

**Review Process:**
1. For each file:
   - Generate parser reports (AST, CFG, PDG, Semantic)
   - Read and analyze the code
   - Cross-reference with parser reports recursively
   - Find and validate issues
   - Check knowledge base before commenting
2. Prepare structured PR comments
3. Return comprehensive review

Start the analysis."""
        
        initial_state: CodeRabbitAgentState = {
            "messages": [HumanMessage(content=input_message)],
            "pr_context": {
                "repo_path": repo_path,
                "files": file_paths
            },
            "knowledge_context": {},
            "files_to_analyze": file_paths,
            "current_file": file_paths[0] if file_paths else None,
            "file_analysis": {},
            "parser_reports": {},
            "issues_found": [],
            "validated_issues": [],
            "comments_to_post": [],
            "current_stage": "initialize",
            "iteration_count": 0,
            "max_iterations": 10
        }
        
        final_state = self.app.invoke(initial_state)
        
        return self._extract_results(final_state)
    
    def _build_review_request(
        self,
        repo_url: str,
        pr_number: Optional[int] = None,
        branch: Optional[str] = None,
        files: Optional[List[str]] = None,
        pr_description: Optional[str] = None
    ) -> str:
        """Build the review request message"""
        
        message_parts = [
            "Please perform a comprehensive CodeRabbit-style code review.",
            "",
            f"**Repository:** {repo_url}"
        ]
        
        if pr_number:
            message_parts.append(f"**Pull Request:** #{pr_number}")
        
        if branch:
            message_parts.append(f"**Branch:** {branch}")
        
        if pr_description:
            message_parts.append(f"\n**PR Description:**\n{pr_description}")
        
        if files:
            files_list = "\n".join([f"  - {f}" for f in files])
            message_parts.append(f"\n**Files to review:**\n{files_list}")
        
        message_parts.extend([
            "",
            "**CodeRabbit Review Process:**",
            "",
            "1. **Initialize**:",
            "   - Clone repository",
            "   - Load knowledge base context",
            "   - Get list of files to review",
            "",
            "2. **For each file**:",
            "   a. **Generate Parser Reports**:",
            "      - Trigger AST, CFG, PDG, Semantic analysis",
            "      - Wait for reports to be generated",
            "   ",
            "   b. **Recursive Analysis**:",
            "      - Read the code file",
            "      - Read parser reports",
            "      - Cross-reference back and forth",
            "      - Identify issues",
            "      - Dig deeper if needed (up to 10 iterations)",
            "   ",
            "   c. **Validate Issues**:",
            "      - Check knowledge base for past learnings",
            "      - Filter out issues maintainers previously accepted",
            "      - Keep only valid, actionable issues",
            "   ",
            "   d. **Prepare Comments**:",
            "      - Format as PR comments",
            "      - Include code suggestions",
            "      - Reference parser evidence",
            "",
            "3. **Finalize**:",
            "   - Compile all comments",
            "   - Generate review summary",
            "   - Return structured output",
            "",
            "**Important**: Only comment on genuine issues. Check knowledge base to avoid repeating comments on patterns maintainers have accepted.",
            "",
            "Start the review process now."
        ])
        
        return "\n".join(message_parts)
    
    def _extract_results(self, final_state: CodeRabbitAgentState) -> Dict[str, Any]:
        """Extract and format results from final state"""
        
        messages = final_state.get("messages", [])
        comments_to_post = final_state.get("comments_to_post", [])
        validated_issues = final_state.get("validated_issues", [])
        
        result = {
            "status": "success",
            "stage": final_state.get("current_stage", "unknown"),
            "pr_context": final_state.get("pr_context", {}),
            "files_analyzed": final_state.get("file_analysis", {}),
            "total_issues_found": len(final_state.get("issues_found", [])),
            "validated_issues_count": len(validated_issues),
            "comments_count": len(comments_to_post),
            "validated_issues": validated_issues,
            "comments": comments_to_post
        }
        
        # Try to extract final formatted review from messages
        for msg in reversed(messages):
            if hasattr(msg, "content"):
                content = msg.content
                if isinstance(content, str):
                    # Try to parse as JSON
                    try:
                        import json
                        parsed = json.loads(content)
                        if "summary" in parsed or "comments" in parsed:
                            result["formatted_review"] = parsed
                            break
                    except (json.JSONDecodeError, ValueError):
                        pass
        
        # If no formatted review found, use last message as raw review
        if "formatted_review" not in result and messages:
            last_message = messages[-1]
            if hasattr(last_message, "content"):
                result["raw_review"] = last_message.content
        
        return result


# Convenience function
def review_pull_request(
    repo_url: str,
    pr_number: Optional[int] = None,
    branch: Optional[str] = None,
    files: Optional[List[str]] = None,
    pr_description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to perform a CodeRabbit-style review.
    
    Args:
        repo_url: GitHub repository URL
        pr_number: Pull request number
        branch: Branch name
        files: List of files to review
        pr_description: PR description
        
    Returns:
        Review results dictionary
    """
    reviewer = CodeRabbitReviewer()
    return reviewer.review_pr(
        repo_url=repo_url,
        pr_number=pr_number,
        branch=branch,
        files=files,
        pr_description=pr_description
    )


# Export
__all__ = [
    'CodeRabbitReviewer',
    'review_pull_request'
]

