"""
Code Review Workflow (DEPRECATED)

⚠️ DEPRECATED: This module is deprecated and will be removed in a future version.
Use the new multi-agent system instead:

    from agent import SupervisorAgent, ReviewRequest, SupervisorConfig
    
    config = SupervisorConfig(use_mock=True)
    supervisor = SupervisorAgent(config=config)
    output, checkpoint = supervisor.run(request)

The new system provides:
- Multi-agent architecture (Parser, Review, Reducer, KB Filter)
- Better security scanning with 13+ patterns
- Complexity analysis
- Knowledge Base integration for filtering
- Checkpointing and resumability
- Structured output for GitHub

Legacy: Orchestrates the code review pipeline using Parsers (AST + Semantic analysis).
"""

import os
import sys
import tempfile
import subprocess
import logging
import warnings
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from .mock_llm import MockLLM

# Emit deprecation warning on import
warnings.warn(
    "CodeReviewWorkflow is deprecated. Use SupervisorAgent from agent module instead. "
    "See agent/__init__.py for the new multi-agent API.",
    DeprecationWarning,
    stacklevel=2
)

logger = logging.getLogger(__name__)

# Try to import KB client, but don't fail if not available
try:
    from .services.kb_client import get_kb_client
except ImportError:
    get_kb_client = lambda: type('MockKB', (), {'enabled': False})()

# Add Parsers directory to path
PARSERS_DIR = Path(__file__).parent.parent.parent / "Parsers"
sys.path.insert(0, str(PARSERS_DIR))


class CodeReviewWorkflow:
    """
    Orchestrates the code review pipeline.
    
    Pipeline:
    1. Clone/access repository
    2. Fetch relevant learnings from Knowledge Base
    3. Run AST analysis on changed files
    4. Run Semantic analysis on changed files
    5. Generate review using LLM (with KB context)
    6. Format output for GitHub
    """
    
    def __init__(self, use_mock_llm: bool = True):
        """
        Initialize the workflow.
        
        Args:
            use_mock_llm: If True, use MockLLM instead of real API calls
        """
        self.use_mock_llm = use_mock_llm
        self.llm = MockLLM() if use_mock_llm else None
        self._pipeline = None
        self.kb_client = get_kb_client()
    
    def _get_pipeline(self):
        """Lazy load the analysis pipeline"""
        if self._pipeline is None:
            try:
                from pipeline import AnalysisPipeline
                self._pipeline = AnalysisPipeline()
            except ImportError as e:
                logger.error(f"Failed to import AnalysisPipeline: {e}")
                raise
        return self._pipeline
    
    def _fetch_kb_context(
        self,
        owner: str,
        repo: str,
        pr_description: Optional[str],
        changed_files: Optional[List[str]]
    ) -> Dict[str, Any]:
        """
        Fetch relevant learnings from Knowledge Base for PR context.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_description: PR title/description
            changed_files: List of changed file paths
            
        Returns:
            Dict with learnings and formatted context
        """
        kb_context = {
            "learnings": [],
            "formatted_context": "",
            "kb_enabled": self.kb_client.enabled
        }
        
        if not self.kb_client.enabled:
            logger.info("KB disabled, skipping context fetch")
            return kb_context
        
        try:
            # Get PR context learnings
            learnings = self.kb_client.get_pr_context_learnings(
                owner=owner,
                repo=repo,
                pr_description=pr_description or "",
                changed_files=changed_files or [],
                k=10
            )
            
            kb_context["learnings"] = learnings
            kb_context["formatted_context"] = self.kb_client.format_learnings_for_prompt(
                learnings, max_learnings=5
            )
            
            logger.info(f"Fetched {len(learnings)} learnings from KB for {owner}/{repo}")
            
        except Exception as e:
            logger.warning(f"Failed to fetch KB context: {e}")
        
        return kb_context
    
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
        Review a pull request.
        
        Args:
            repo_url: GitHub repo URL or shorthand (owner/repo)
            pr_number: PR number
            branch: Branch to review
            changed_files: List of changed file paths
            pr_description: Description of the PR
            generate_tests: Whether to generate unit tests
            
        Returns:
            Review result with formatted comments
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting review for {repo_url} (PR #{pr_number})")
        
        try:
            # Parse owner/repo from URL
            owner, repo = self._parse_repo_url(repo_url)
            
            # Fetch KB context first
            kb_context = self._fetch_kb_context(
                owner=owner,
                repo=repo,
                pr_description=pr_description,
                changed_files=changed_files
            )
            
            repo_path = self._clone_repository(repo_url, branch)
            
            if not changed_files:
                changed_files = self._discover_files(repo_path)
            
            all_reviews = []
            analysis_results = {}
            
            for file_path in changed_files or []:
                full_path = os.path.join(repo_path, file_path)
                
                if not os.path.exists(full_path):
                    logger.warning(f"File not found: {full_path}")
                    continue
                
                file_analysis = self._analyze_file(full_path)
                analysis_results[file_path] = file_analysis
                
                # Pass KB context to review generation
                review = self._generate_review(
                    file_analysis, 
                    file_path,
                    kb_context=kb_context
                )
                all_reviews.append(review)
            
            formatted_review = self._format_for_github(
                all_reviews, 
                pr_description,
                kb_context=kb_context
            )
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "status": "success",
                "repo_url": repo_url,
                "pr_number": pr_number,
                "branch": branch,
                "files_reviewed": len(changed_files or []),
                "analysis_results": analysis_results,
                "formatted_review": formatted_review,
                "duration_seconds": duration,
                "mock_llm": self.use_mock_llm,
                "kb_learnings_used": len(kb_context.get("learnings", [])),
                "unit_tests": {} if not generate_tests else self._generate_tests(changed_files, repo_path)
            }
            
        except Exception as e:
            logger.error(f"Review failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "repo_url": repo_url,
                "pr_number": pr_number
            }
    
    def _parse_repo_url(self, repo_url: str) -> tuple:
        """Parse owner and repo from URL or shorthand."""
        # Handle shorthand (owner/repo)
        if "/" in repo_url and not repo_url.startswith("http"):
            parts = repo_url.split("/")
            return parts[0], parts[1].replace(".git", "")
        
        # Handle full URL
        if "github.com" in repo_url:
            parts = repo_url.rstrip("/").rstrip(".git").split("/")
            return parts[-2], parts[-1]
        
        return "unknown", "unknown"
    
    def _generate_review(
        self, 
        analysis: Dict, 
        file_path: str,
        kb_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate review for a file using LLM with KB context"""
        if self.use_mock_llm:
            review = self.llm.generate_review(
                ast_data=analysis.get("ast"),
                semantic_data=analysis.get("semantic"),
                file_path=file_path
            )
            
            # Add KB context to the review if available
            if kb_context and kb_context.get("learnings"):
                review["kb_context_applied"] = True
                review["learnings_considered"] = len(kb_context["learnings"])
            
            return review
        raise NotImplementedError("Real LLM integration not yet implemented")
    
    def _clone_repository(self, repo_url: str, branch: Optional[str] = None) -> str:
        """Clone repository to temporary directory"""
        temp_dir = tempfile.mkdtemp(prefix="openrabbit_")
        
        if not repo_url.startswith("http"):
            repo_url = f"https://github.com/{repo_url}.git"
        elif not repo_url.endswith(".git"):
            repo_url = f"{repo_url}.git"
        
        cmd = ["git", "clone", "--depth", "1"]
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([repo_url, temp_dir])
        
        logger.info(f"Cloning {repo_url} to {temp_dir}")
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to clone repository: {e.stderr.decode()}")
        
        return temp_dir
    
    def _discover_files(self, repo_path: str) -> List[str]:
        """Discover analyzable files in repository"""
        supported_extensions = {".py", ".js", ".jsx", ".ts", ".tsx"}
        files = []
        
        for root, _, filenames in os.walk(repo_path):
            if any(part.startswith(".") for part in root.split(os.sep)) or "node_modules" in root:
                continue
            
            for filename in filenames:
                ext = os.path.splitext(filename)[1]
                if ext in supported_extensions:
                    rel_path = os.path.relpath(os.path.join(root, filename), repo_path)
                    files.append(rel_path)
        
        return files[:20]
    
    def _analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Run AST and Semantic analysis on a file"""
        results = {"ast": None, "semantic": None, "file_path": file_path}
        
        try:
            pipeline = self._get_pipeline()
            ast_tree = pipeline.parse_file(file_path)
            results["ast"] = self._extract_ast_summary(ast_tree)
            
            semantic_graph = pipeline.build_semantic()
            results["semantic"] = self._extract_semantic_summary(semantic_graph)
            
        except Exception as e:
            logger.error(f"Analysis failed for {file_path}: {e}")
            results["error"] = str(e)
        
        return results
    
    def _extract_ast_summary(self, ast_tree) -> Dict[str, Any]:
        """Extract summary from AST tree"""
        if ast_tree is None:
            return {}
        return {"type": "ast_summary", "summary": {"parsed": True}, "functions": [], "classes": []}
    
    def _extract_semantic_summary(self, semantic_graph) -> Dict[str, Any]:
        """Extract summary from semantic graph"""
        if semantic_graph is None:
            return {}
        return {"type": "semantic_summary", "nodes": [], "relations": []}
    
    def _format_for_github(
        self, 
        reviews: List[Dict], 
        pr_description: Optional[str] = None,
        kb_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Format review results as GitHub PR review format"""
        comments = []
        total_issues = 0
        
        for review in reviews:
            file_path = review.get("file_path", "unknown")
            issues = review.get("issues", [])
            total_issues += len(issues)
            
            for issue in issues:
                comments.append({
                    "path": file_path,
                    "line": issue.get("line", 1),
                    "body": self._format_issue_body(issue)
                })
        
        summary = self._build_summary(reviews, total_issues, kb_context)
        return {"summary": summary, "comments": comments}
    
    def _build_summary(
        self, 
        reviews: List[Dict], 
        total_issues: int,
        kb_context: Optional[Dict] = None
    ) -> str:
        """Build summary text for the review"""
        parts = [f"**🤖 Open Rabbit Review**\n", f"Analyzed {len(reviews)} file(s), found {total_issues} issue(s).\n"]
        
        # Add KB learnings info if available
        if kb_context and kb_context.get("learnings"):
            num_learnings = len(kb_context["learnings"])
            parts.append(f"\n📚 *Review enhanced with {num_learnings} relevant learning(s) from past feedback.*\n")
        
        if total_issues > 0:
            severity_counts = {}
            for review in reviews:
                for issue in review.get("issues", []):
                    sev = issue.get("severity", "unknown")
                    severity_counts[sev] = severity_counts.get(sev, 0) + 1
            
            if severity_counts:
                parts.append("\n**Issues by severity:**\n")
                for sev, count in sorted(severity_counts.items()):
                    emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
                    parts.append(f"- {emoji} {sev.capitalize()}: {count}\n")
        
        return "".join(parts)
    
    def _format_issue_body(self, issue: Dict) -> str:
        """Format a single issue as markdown"""
        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(issue.get("severity", ""), "⚪")
        body = f"{emoji} **{issue.get('type', 'Issue').replace('_', ' ').title()}**\n\n"
        body += f"{issue.get('message', '')}\n\n"
        if issue.get("suggestion"):
            body += f"💡 **Suggestion:** {issue.get('suggestion')}\n"
        return body
    
    def _generate_tests(self, files: List[str], repo_path: str) -> Dict[str, Any]:
        """Generate unit tests for files (placeholder)"""
        return {"framework": "pytest", "test_count": 0, "files_generated": []}
