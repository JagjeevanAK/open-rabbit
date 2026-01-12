"""
GitHub Bot Comment Service
Handles posting code review comments to GitHub via the bot
"""

import os
import requests
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

BOT_URL = os.getenv("BOT_URL", "http://localhost:3000")


class GitHubCommentService:
    """Service for posting comments to GitHub via the bot"""
    
    def __init__(self, bot_url: str = BOT_URL, test_mode: bool = False):
        self.bot_url = bot_url.rstrip('/')
        self.test_mode = test_mode
        
        # Use test endpoints when in test mode
        if test_mode:
            self.comment_endpoint = f"{self.bot_url}/test/trigger-review"
            self.review_endpoint = f"{self.bot_url}/test/trigger-review"
        else:
            self.comment_endpoint = f"{self.bot_url}/trigger-comment"
            self.review_endpoint = f"{self.bot_url}/trigger-review"
        
        self.health_endpoint = f"{self.bot_url}/health"
    
    def post_review(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        installation_id: int = 0,
        body: Optional[str] = None,
        comments: Optional[List[Dict[str, Any]]] = None,
        event: str = "COMMENT",
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Post a full PR review with summary and inline comments.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: PR number
            installation_id: GitHub App installation ID (not used in test mode)
            body: Summary comment (markdown)
            comments: List of inline comments [{path, line, body, start_line?}]
            event: Review event type (COMMENT, APPROVE, REQUEST_CHANGES)
            dry_run: If true, save to file instead of posting (test mode only)
            
        Returns:
            Response from bot with success status
        """
        payload = {
            "owner": owner,
            "repo": repo,
            "pull_number": pull_number,
            "event": event,
        }
        
        # Only include installation_id for non-test mode
        if not self.test_mode:
            payload["installation_id"] = installation_id
        
        # Include dry_run for test mode
        if self.test_mode:
            payload["dry_run"] = dry_run
        
        if body:
            payload["body"] = body
        
        if comments:
            payload["comments"] = comments
        
        try:
            mode_str = "[TEST MODE] " if self.test_mode else ""
            logger.info(f"{mode_str}Creating review for {owner}/{repo}#{pull_number} with {len(comments or [])} inline comments")
            
            response = requests.post(
                self.review_endpoint,
                json=payload,
                timeout=60  # Longer timeout for reviews with many comments
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"{mode_str}Review created successfully: {result}")
            return {
                "success": True,
                "message": result.get("message", "Review created"),
                "review_id": result.get("review_id"),
                "comments_posted": result.get("comments_posted", 0),
                "html_url": result.get("html_url"),
                "output_file": result.get("output_file"),  # For dry run mode
                "dry_run": result.get("dry_run", False),
                "status_code": response.status_code
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create review: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create review on GitHub"
            }
    
    def post_review_comment(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        body: str,
        installation_id: int
    ) -> Dict[str, Any]:
        """
        Post a single comment to a PR (legacy method).
        
        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: PR number
            body: Comment body (markdown supported)
            installation_id: GitHub App installation ID
            
        Returns:
            Response from bot with success status
        """
        payload = {
            "owner": owner,
            "repo": repo,
            "pull_number": pull_number,
            "body": body,
            "installation_id": installation_id
        }
        
        try:
            logger.info(f"Posting comment to {owner}/{repo}#{pull_number}")
            
            response = requests.post(
                self.comment_endpoint,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Comment posted successfully: {result}")
            return {
                "success": True,
                "message": result.get("message", "Comment posted"),
                "status_code": response.status_code
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to post comment: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to post comment to GitHub"
            }
    
    def format_review_as_comment(self, review_result: Dict[str, Any]) -> str:
        """
        Format review result as a GitHub comment with markdown.
        
        DEPRECATED: Use post_review_from_result() instead which supports inline comments.
        
        Args:
            review_result: Review result from workflow
            
        Returns:
            Formatted markdown string
        """
        formatted_output = review_result.get("formatted_review", {})
        unit_tests = review_result.get("unit_tests", {})
        
        comment_parts = []
        
        comment_parts.append("# 🤖 Open Rabbit Code Review\n")
        
        # Summary section
        if "summary" in formatted_output:
            comment_parts.append("## 📋 Summary\n")
            comment_parts.append(f"{formatted_output['summary']}\n")
        
        # Comments section
        if "comments" in formatted_output and formatted_output["comments"]:
            comment_parts.append("## 💬 Code Review Comments\n")
            
            for idx, comment in enumerate(formatted_output["comments"], 1):
                file_path = comment.get("path", "Unknown file")
                line = comment.get("line", "N/A")
                body = comment.get("body", "No comment")
                
                comment_parts.append(f"### {idx}. `{file_path}` (Line {line})\n")
                comment_parts.append(f"{body}\n")
        
        # Unit tests section
        if unit_tests and unit_tests.get("files_generated"):
            comment_parts.append("## 🧪 Unit Tests Generated\n")
            comment_parts.append(f"**Framework:** {unit_tests.get('framework', 'Unknown')}\n")
            comment_parts.append(f"**Tests Created:** {unit_tests.get('test_count', 0)}\n")
            comment_parts.append("**Files:**\n")
            for file in unit_tests.get("files_generated", []):
                comment_parts.append(f"- `{file}`\n")
        
        # Footer
        comment_parts.append("\n---")
        comment_parts.append("\n*Review generated by [Open Rabbit](https://github.com/open-rabbit)*")
        
        return "\n".join(comment_parts)
    
    def post_review_from_result(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        review_result: Dict[str, Any],
        installation_id: int = 0,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Post a full review from workflow result with inline comments.
        
        This is the preferred method for posting reviews as it supports:
        - Summary comment at the top
        - Inline comments on specific lines
        - Rich formatting with collapsible sections
        
        Args:
            owner: Repository owner
            repo: Repository name
            pull_number: PR number
            review_result: Review result from workflow
            installation_id: GitHub App installation ID (not used in test mode)
            dry_run: If true, save to file instead of posting (test mode only)
            
        Returns:
            Result of posting review
        """
        formatted_review = review_result.get("formatted_review", {})
        
        # Support both "body" (new format from CommentFormatterAgent) and "summary" (legacy)
        summary = formatted_review.get("body") or formatted_review.get("summary", "")
        comments = formatted_review.get("comments", [])
        
        # Add footer to summary
        if summary:
            summary += "\n\n---\n_Review generated by [Open Rabbit](https://github.com/open-rabbit)_"
        
        return self.post_review(
            owner=owner,
            repo=repo,
            pull_number=pull_number,
            installation_id=installation_id,
            body=summary,
            comments=comments,
            event="COMMENT",
            dry_run=dry_run
        )
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check if bot service is healthy.
        
        Returns:
            Health status from bot
        """
        try:
            response = requests.get(self.health_endpoint, timeout=5)
            response.raise_for_status()
            return {
                "healthy": True,
                "status": response.json()
            }
        except Exception as e:
            logger.warning(f"Bot health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e)
            }


def post_review_to_github(
    owner: str,
    repo: str,
    pull_number: int,
    review_result: Dict[str, Any],
    installation_id: int = 0,
    test_mode: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to post review result to GitHub with inline comments.
    
    Args:
        owner: Repository owner
        repo: Repository name
        pull_number: PR number
        review_result: Complete review result from workflow
        installation_id: GitHub App installation ID (not used in test mode)
        test_mode: If true, use test endpoints (PAT auth)
        dry_run: If true, save to file instead of posting (test mode only)
        
    Returns:
        Result of posting review
    """
    service = GitHubCommentService(test_mode=test_mode)
    
    return service.post_review_from_result(
        owner=owner,
        repo=repo,
        pull_number=pull_number,
        review_result=review_result,
        installation_id=installation_id,
        dry_run=dry_run
    )
