"""
Code Parser Tool for LangChain Agent

This tool integrates with the Parsers Celery worker to analyze source code files
and provide AST, CFG, and PDG analysis for enhanced code review capabilities.

The tool triggers the Parsers agent/worker which performs:
1. AST (Abstract Syntax Tree) parsing
2. CFG (Control Flow Graph) generation
3. PDG (Program Dependence Graph) analysis
4. LangGraph workflow for code review insights

Returns a formatted report suitable for the main agent's context.
"""

from langchain_core.tools import tool
from typing import Optional, Dict, Any, List
import os
import sys
import json
from pathlib import Path

# Add Parsers directory to path
PARSERS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "Parsers")
if PARSERS_DIR not in sys.path:
    sys.path.insert(0, PARSERS_DIR)

# Import Celery client from Parsers
try:
    from client.client import (
        submit_file_for_processing,
        submit_pipeline_only,
        get_task_status,
        wait_for_task
    )
    CELERY_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Celery client not available: {e}")
    CELERY_AVAILABLE = False


class ParserAgentClient:
    """Client for triggering the Parsers Celery worker agent."""
    
    SUPPORTED_LANGUAGES = ["python", "javascript", "typescript", "tsx"]
    EXTENSION_MAP = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'tsx'
    }
    
    def __init__(self, timeout: int = 300):
        """
        Initialize the parser agent client.
        
        Args:
            timeout: Maximum time to wait for task completion (seconds)
        """
        self.timeout = timeout
        self.celery_available = CELERY_AVAILABLE
    
    def detect_language(self, file_path: str) -> str:
        """
        Detect programming language from file extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Detected language
        """
        ext = Path(file_path).suffix.lower()
        return self.EXTENSION_MAP.get(ext, 'python')
    
    def analyze_file(
        self,
        file_path: str,
        output_dir: str = "output/parser_reports",
        wait: bool = True
    ) -> Dict[str, Any]:
        """
        Trigger the Parsers worker to analyze a source code file.
        
        This submits the file to the Celery worker which runs:
        1. AST -> CFG -> PDG pipeline
        2. LangGraph workflow for analysis
        3. Generates formatted reports
        
        Args:
            file_path: Path to the source file
            output_dir: Directory to store analysis outputs
            wait: Whether to wait for completion
            
        Returns:
            Dictionary with analysis results and report
        """
        if not self.celery_available:
            return {
                "success": False,
                "error": "Celery client not available. Make sure Redis is running and Parsers worker is accessible."
            }
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"File not found: {file_path}"
                }
            
            # Submit task to Celery worker
            task_id = submit_file_for_processing(file_path, output_dir)
            
            if not wait:
                return {
                    "success": True,
                    "task_id": task_id,
                    "status": "submitted",
                    "message": f"Task submitted. Use task_id {task_id} to check status."
                }
            
            # Wait for completion
            result = wait_for_task(task_id, timeout=self.timeout, poll_interval=2)
            
            # Handle chained task result
            if isinstance(result, str):
                # Result is a task ID from chain, get the actual workflow result
                workflow_result = wait_for_task(result, timeout=self.timeout, poll_interval=2)
                result = workflow_result
            
            # Format the result into a concise report
            if isinstance(result, dict) and result.get("status") == "success":
                return self._format_success_result(result, file_path)
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Analysis failed") if isinstance(result, dict) else str(result),
                    "file_path": file_path
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to analyze file: {str(e)}",
                "file_path": file_path
            }
    
    def analyze_pipeline_only(
        self,
        file_path: str,
        output_dir: str = "output/parser_reports"
    ) -> Dict[str, Any]:
        """
        Run pipeline analysis only (AST, CFG, PDG) without workflow.
        
        Args:
            file_path: Path to the source file
            output_dir: Directory to store outputs
            
        Returns:
            Dictionary with pipeline results
        """
        if not self.celery_available:
            return {
                "success": False,
                "error": "Celery client not available"
            }
        
        try:
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"File not found: {file_path}"
                }
            
            task_id = submit_pipeline_only(file_path, output_dir)
            result = wait_for_task(task_id, timeout=self.timeout, poll_interval=2)
            
            if isinstance(result, dict) and result.get("status") == "success":
                return self._format_pipeline_result(result, file_path)
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Pipeline failed") if isinstance(result, dict) else str(result)
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Pipeline analysis failed: {str(e)}",
                "file_path": file_path
            }
    
    def _format_success_result(self, result: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Format successful analysis result into a concise report."""
        return {
            "success": True,
            "file_path": file_path,
            "language": result.get("language", "unknown"),
            "output_dir": result.get("output_dir", ""),
            "analysis_summary": result.get("analysis_summary", ""),
            "pdg_summary": result.get("pdg_summary", ""),
            "review_output": result.get("review_output", ""),
            "report": self._generate_compact_report(result)
        }
    
    def _format_pipeline_result(self, result: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Format pipeline-only result."""
        return {
            "success": True,
            "file_path": file_path,
            "language": result.get("language", "unknown"),
            "output_dir": result.get("output_dir", ""),
            "summary": result.get("summary", ""),
            "files_generated": result.get("files_generated", [])
        }
    
    def _generate_compact_report(self, result: Dict[str, Any]) -> str:
        """Generate a compact, readable report for the agent."""
        report_lines = []
        
        report_lines.append(f"=== CODE ANALYSIS REPORT ===")
        report_lines.append(f"File: {result.get('file_analyzed', 'N/A')}")
        report_lines.append(f"Language: {result.get('language', 'N/A')}")
        report_lines.append("")
        
        report_lines.append("--- AST Analysis ---")
        report_lines.append(result.get("analysis_summary", "No AST summary available"))
        report_lines.append("")
        
        report_lines.append("--- PDG Analysis ---")
        report_lines.append(result.get("pdg_summary", "No PDG summary available"))
        report_lines.append("")
        
        report_lines.append("--- Code Review Insights ---")
        report_lines.append(result.get("review_output", "No review insights available"))
        
        return "\n".join(report_lines)


# Create global client instance
parser_agent_client = ParserAgentClient(
    timeout=int(os.getenv("PARSER_TIMEOUT", "300"))
)


@tool
def parse_code_file(
    file_path: str,
    include_workflow: bool = True
) -> str:
    """
    Trigger the Parsers agent to analyze a source code file with deep static analysis.
    
    This tool submits the file to the Parsers Celery worker which:
    1. Parses code into AST (Abstract Syntax Tree)
    2. Builds CFG (Control Flow Graph)
    3. Generates PDG (Program Dependence Graph)
    4. Runs LangGraph workflow for AI-powered insights
    5. Returns a formatted report with key findings
    
    Use this tool when you need to:
    - Understand code structure and complexity
    - Analyze control flow and logic paths
    - Track data and control dependencies
    - Get AI-powered code review insights
    
    Args:
        file_path: Absolute path to the source code file to analyze
        include_workflow: Whether to run the full workflow (True) or pipeline only (False)
    
    Returns:
        JSON string with analysis report including:
        - AST analysis summary
        - PDG dependency analysis
        - Code review insights from LangGraph workflow
    
    Example:
        >>> parse_code_file("/path/to/file.py", include_workflow=True)
    """
    try:
        if include_workflow:
            result = parser_agent_client.analyze_file(file_path)
        else:
            result = parser_agent_client.analyze_pipeline_only(file_path)
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to parse file: {str(e)}",
            "file_path": file_path
        })


@tool
def analyze_changed_files(
    file_paths: List[str]
) -> str:
    """
    Analyze multiple source code files from a pull request or change set.
    
    This tool batch-processes multiple files through the Parsers agent,
    providing comprehensive analysis for each file.
    
    Args:
        file_paths: List of absolute file paths to analyze
    
    Returns:
        JSON string with analysis results for all files
    
    Example:
        >>> analyze_changed_files(["/path/file1.py", "/path/file2.py"])
    """
    try:
        results = {}
        errors = []
        
        for file_path in file_paths:
            result = parser_agent_client.analyze_file(file_path)
            
            if result.get("success"):
                results[file_path] = result
            else:
                errors.append({
                    "file_path": file_path,
                    "error": result.get("error", "Unknown error")
                })
        
        return json.dumps({
            "success": len(errors) == 0,
            "analyzed_files": len(results),
            "results": results,
            "errors": errors
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to analyze files: {str(e)}",
            "file_paths": file_paths
        })


@tool
def get_parser_capabilities() -> str:
    """
    Get information about parser capabilities and supported languages.
    
    Returns:
        JSON string with parser capabilities information
    """
    return json.dumps({
        "celery_available": CELERY_AVAILABLE,
        "supported_languages": ParserAgentClient.SUPPORTED_LANGUAGES,
        "file_extensions": ParserAgentClient.EXTENSION_MAP,
        "analysis_capabilities": [
            "AST (Abstract Syntax Tree) parsing",
            "CFG (Control Flow Graph) generation",
            "PDG (Program Dependence Graph) analysis",
            "LangGraph workflow for AI insights",
            "Async processing via Celery workers"
        ],
        "requirements": [
            "Redis server running (localhost:6379)",
            "Parsers Celery worker running",
            "Supported file extensions: .py, .js, .jsx, .ts, .tsx"
        ]
    }, indent=2)


# Export tools for agent integration
__all__ = [
    'parse_code_file',
    'analyze_changed_files',
    'get_parser_capabilities',
    'ParserAgentClient',
    'parser_agent_client'
]
