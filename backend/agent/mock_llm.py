"""
Mock LLM Provider

Mock implementation for testing without real API calls.
"""

from typing import Dict, Any


class MockLLM:
    """Mock LLM for testing without API calls"""
    
    def __init__(self):
        self.call_count = 0
    
    def generate_review(
        self, 
        ast_data: Dict, 
        semantic_data: Dict, 
        file_path: str
    ) -> Dict[str, Any]:
        """
        Generate a mock code review based on analysis data.
        
        Args:
            ast_data: AST analysis results
            semantic_data: Semantic analysis results
            file_path: Path to the analyzed file
            
        Returns:
            Mock review with issues extracted from analysis
        """
        self.call_count += 1
        issues = []
        
        # Extract issues from AST data
        if ast_data:
            issues.extend(self._extract_ast_issues(ast_data))
        
        # Extract issues from Semantic data
        if semantic_data:
            issues.extend(self._extract_semantic_issues(semantic_data))
        
        return {
            "file_path": file_path,
            "issues": issues,
            "summary": f"Found {len(issues)} issue(s) in {file_path}",
            "mock": True
        }
    
    def _extract_ast_issues(self, ast_data: Dict) -> list:
        """Extract issues from AST analysis"""
        issues = []
        functions = ast_data.get("functions", [])
        
        for func in functions:
            # Check for high complexity
            if func.get("complexity", 0) > 10:
                issues.append({
                    "type": "high_complexity",
                    "severity": "medium",
                    "line": func.get("start_line", 1),
                    "message": f"Function '{func.get('name')}' has high complexity ({func.get('complexity')}). Consider refactoring.",
                    "suggestion": f"Break down '{func.get('name')}' into smaller functions."
                })
            
            # Check for missing docstring
            if not func.get("docstring") and func.get("parameters"):
                issues.append({
                    "type": "missing_documentation",
                    "severity": "low",
                    "line": func.get("start_line", 1),
                    "message": f"Function '{func.get('name')}' lacks documentation.",
                    "suggestion": f"Add a docstring describing what '{func.get('name')}' does."
                })
        
        return issues
    
    def _extract_semantic_issues(self, semantic_data: Dict) -> list:
        """Extract issues from Semantic analysis"""
        issues = []
        nodes = semantic_data.get("nodes", [])
        
        for node in nodes:
            if node.get("type") == "variable" and not node.get("references"):
                issues.append({
                    "type": "unused_variable",
                    "severity": "low",
                    "line": node.get("line", 1),
                    "message": f"Variable '{node.get('name')}' appears to be unused.",
                    "suggestion": f"Remove unused variable '{node.get('name')}' or use it."
                })
        
        return issues
