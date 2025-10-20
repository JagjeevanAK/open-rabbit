"""
Parser Reports Reader Tool

Tools for reading and analyzing parser output reports (AST, CFG, PDG, Semantic)
from the Parsers/output directory.
"""

from langchain_core.tools import tool
from typing import Dict, Any, List, Optional
import json
from pathlib import Path
import os


class ParserReportsReader:
    """Client for reading parser output reports"""
    
    def __init__(self, output_dir: str = None):
        """
        Initialize the parser reports reader.
        
        Args:
            output_dir: Directory containing parser reports (default: Parsers/output)
        """
        if output_dir is None:
            # Default to Parsers/output relative to backend
            backend_dir = Path(__file__).parent.parent.parent
            self.output_dir = backend_dir.parent / "Parsers" / "output"
        else:
            self.output_dir = Path(output_dir)
    
    def find_report_files(self, file_base_name: str) -> Dict[str, Optional[Path]]:
        """
        Find all parser report files for a given source file.
        
        Args:
            file_base_name: Base name of the source file (without extension)
            
        Returns:
            Dictionary with paths to AST, CFG, PDG, and Semantic reports
        """
        reports = {
            "ast": None,
            "cfg": None,
            "pdg": None,
            "semantic": None
        }
        
        if not self.output_dir.exists():
            return reports
        
        # Look for report files with the base name
        for report_type in reports.keys():
            pattern = f"{file_base_name}_{report_type}.json"
            report_files = list(self.output_dir.glob(pattern))
            
            if report_files:
                reports[report_type] = report_files[0]
        
        return reports
    
    def read_report(self, report_path: Path) -> Optional[Dict[str, Any]]:
        """
        Read a parser report file.
        
        Args:
            report_path: Path to the report file
            
        Returns:
            Report data as dictionary
        """
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {"error": f"Failed to read report: {str(e)}"}
    
    def get_all_reports(self, file_base_name: str) -> Dict[str, Any]:
        """
        Get all parser reports for a file.
        
        Args:
            file_base_name: Base name of the source file
            
        Returns:
            Dictionary containing all report data
        """
        report_paths = self.find_report_files(file_base_name)
        reports = {}
        
        for report_type, path in report_paths.items():
            if path and path.exists():
                reports[report_type] = self.read_report(path)
            else:
                reports[report_type] = None
        
        return reports
    
    def get_ast_report(self, file_base_name: str) -> Optional[Dict[str, Any]]:
        """Get AST report for a file"""
        report_paths = self.find_report_files(file_base_name)
        if report_paths["ast"]:
            return self.read_report(report_paths["ast"])
        return None
    
    def get_cfg_report(self, file_base_name: str) -> Optional[Dict[str, Any]]:
        """Get CFG report for a file"""
        report_paths = self.find_report_files(file_base_name)
        if report_paths["cfg"]:
            return self.read_report(report_paths["cfg"])
        return None
    
    def get_pdg_report(self, file_base_name: str) -> Optional[Dict[str, Any]]:
        """Get PDG report for a file"""
        report_paths = self.find_report_files(file_base_name)
        if report_paths["pdg"]:
            return self.read_report(report_paths["pdg"])
        return None
    
    def get_semantic_report(self, file_base_name: str) -> Optional[Dict[str, Any]]:
        """Get Semantic Graph report for a file"""
        report_paths = self.find_report_files(file_base_name)
        if report_paths["semantic"]:
            return self.read_report(report_paths["semantic"])
        return None
    
    def extract_issues_from_reports(self, reports: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract potential issues from all parser reports.
        
        Args:
            reports: Dictionary containing all report types
            
        Returns:
            List of potential issues found
        """
        issues = []
        
        # AST issues
        if reports.get("ast"):
            ast_data = reports["ast"]
            summary = ast_data.get("summary", {})
            
            # Check function complexity
            functions = ast_data.get("functions", [])
            for func in functions:
                if func.get("complexity", 0) > 10:
                    issues.append({
                        "type": "high_complexity",
                        "source": "AST",
                        "severity": "medium",
                        "line": func.get("start_line"),
                        "function": func.get("name"),
                        "complexity": func.get("complexity"),
                        "message": f"Function '{func.get('name')}' has high cyclomatic complexity ({func.get('complexity')})"
                    })
        
        # CFG issues
        if reports.get("cfg"):
            cfg_data = reports["cfg"]
            summary = cfg_data.get("summary", {})
            
            # Unreachable code
            unreachable = cfg_data.get("unreachable_blocks", [])
            for block in unreachable:
                issues.append({
                    "type": "unreachable_code",
                    "source": "CFG",
                    "severity": "high",
                    "line": block.get("start_line"),
                    "message": f"Unreachable code detected at line {block.get('start_line')}"
                })
            
            # High cyclomatic complexity
            complexity = summary.get("cyclomatic_complexity", 0)
            if complexity > 15:
                issues.append({
                    "type": "high_cyclomatic_complexity",
                    "source": "CFG",
                    "severity": "medium",
                    "complexity": complexity,
                    "message": f"High cyclomatic complexity ({complexity}). Consider refactoring."
                })
        
        # PDG issues
        if reports.get("pdg"):
            pdg_data = reports["pdg"]
            
            # Complex data dependencies
            data_deps = pdg_data.get("data_dependencies", [])
            if len(data_deps) > 50:
                issues.append({
                    "type": "complex_dependencies",
                    "source": "PDG",
                    "severity": "medium",
                    "count": len(data_deps),
                    "message": f"High number of data dependencies ({len(data_deps)}). Consider simplifying."
                })
        
        # Semantic issues
        if reports.get("semantic"):
            semantic_data = reports["semantic"]
            summary = semantic_data.get("summary", {})
            
            # Check for missing documentation
            functions = semantic_data.get("functions", [])
            for func in functions:
                if not func.get("docstring") and func.get("parameters", []):
                    issues.append({
                        "type": "missing_documentation",
                        "source": "Semantic",
                        "severity": "low",
                        "line": func.get("start_line"),
                        "function": func.get("name"),
                        "message": f"Function '{func.get('name')}' lacks documentation"
                    })
        
        return issues


# Global instance
reports_reader = ParserReportsReader()


@tool
def read_parser_reports(file_path: str) -> str:
    """
    Read all parser reports (AST, CFG, PDG, Semantic) for a given source file.
    
    This tool reads the pre-generated parser reports from Parsers/output directory.
    The reports must be generated first using the Parsers pipeline.
    
    Args:
        file_path: Path to the source file (used to find corresponding reports)
    
    Returns:
        JSON string containing all parser reports and extracted issues
    
    Example:
        >>> read_parser_reports("/path/to/file.py")
    """
    try:
        # Extract base name from file path
        base_name = Path(file_path).stem
        
        # Get all reports
        reports = reports_reader.get_all_reports(base_name)
        
        # Extract issues
        issues = reports_reader.extract_issues_from_reports(reports)
        
        # Check which reports are available
        available_reports = [k for k, v in reports.items() if v is not None]
        
        result = {
            "success": True,
            "file_path": file_path,
            "base_name": base_name,
            "available_reports": available_reports,
            "reports": reports,
            "issues_found": len(issues),
            "issues": issues
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to read parser reports: {str(e)}",
            "file_path": file_path
        })


@tool
def get_parser_report_summary(file_path: str) -> str:
    """
    Get a concise summary of parser reports for a file.
    
    This is useful for quick checks without loading full report data.
    
    Args:
        file_path: Path to the source file
    
    Returns:
        JSON string with summary statistics
    
    Example:
        >>> get_parser_report_summary("/path/to/file.py")
    """
    try:
        base_name = Path(file_path).stem
        reports = reports_reader.get_all_reports(base_name)
        issues = reports_reader.extract_issues_from_reports(reports)
        
        summary = {
            "success": True,
            "file_path": file_path,
            "reports_available": {},
            "total_issues": len(issues),
            "issues_by_severity": {
                "high": len([i for i in issues if i.get("severity") == "high"]),
                "medium": len([i for i in issues if i.get("severity") == "medium"]),
                "low": len([i for i in issues if i.get("severity") == "low"])
            },
            "issues_by_source": {}
        }
        
        # Count issues by source
        for issue in issues:
            source = issue.get("source", "unknown")
            summary["issues_by_source"][source] = summary["issues_by_source"].get(source, 0) + 1
        
        # Add report availability
        for report_type, data in reports.items():
            if data:
                summary["reports_available"][report_type] = True
                
                # Add key metrics from each report
                if report_type == "ast" and data.get("summary"):
                    summary["ast_metrics"] = {
                        "functions": data["summary"].get("function_count", 0),
                        "variables": data["summary"].get("variable_count", 0)
                    }
                elif report_type == "cfg" and data.get("summary"):
                    summary["cfg_metrics"] = {
                        "blocks": data["summary"].get("total_blocks", 0),
                        "complexity": data["summary"].get("cyclomatic_complexity", 0),
                        "unreachable": data["summary"].get("unreachable_blocks", 0)
                    }
                elif report_type == "pdg" and data.get("summary"):
                    summary["pdg_metrics"] = {
                        "nodes": data["summary"].get("node_count", 0),
                        "data_deps": data["summary"].get("data_dependency_count", 0),
                        "control_deps": data["summary"].get("control_dependency_count", 0)
                    }
                elif report_type == "semantic" and data.get("summary"):
                    summary["semantic_metrics"] = {
                        "nodes": data["summary"].get("total_nodes", 0),
                        "functions": data["summary"].get("function_count", 0),
                        "classes": data["summary"].get("class_count", 0)
                    }
            else:
                summary["reports_available"][report_type] = False
        
        return json.dumps(summary, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to get summary: {str(e)}",
            "file_path": file_path
        })


@tool
def check_specific_issue_in_reports(
    file_path: str,
    issue_type: str,
    line_number: Optional[int] = None
) -> str:
    """
    Check if a specific type of issue exists in the parser reports.
    
    Useful for validating if an issue detected by the agent is also
    present in the static analysis reports.
    
    Args:
        file_path: Path to the source file
        issue_type: Type of issue to check (e.g., "high_complexity", "unreachable_code")
        line_number: Optional line number to check
    
    Returns:
        JSON string with issue confirmation
    
    Example:
        >>> check_specific_issue_in_reports("/path/file.py", "high_complexity", 42)
    """
    try:
        base_name = Path(file_path).stem
        reports = reports_reader.get_all_reports(base_name)
        issues = reports_reader.extract_issues_from_reports(reports)
        
        # Filter issues by type
        matching_issues = [i for i in issues if i.get("type") == issue_type]
        
        # Further filter by line number if provided
        if line_number is not None:
            matching_issues = [
                i for i in matching_issues 
                if i.get("line") == line_number
            ]
        
        result = {
            "success": True,
            "file_path": file_path,
            "issue_type": issue_type,
            "line_number": line_number,
            "found": len(matching_issues) > 0,
            "count": len(matching_issues),
            "issues": matching_issues
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to check issue: {str(e)}",
            "file_path": file_path
        })


# Export tools
__all__ = [
    'read_parser_reports',
    'get_parser_report_summary',
    'check_specific_issue_in_reports',
    'ParserReportsReader',
    'reports_reader'
]

