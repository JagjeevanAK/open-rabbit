"""
Analysis Pipeline: AST + Semantic
Orchestrates AST parsing and Semantic graph analysis.
"""

import json
from typing import Dict, Optional, Any, Union
from pathlib import Path

from ast_module.ast_parser import parse_code, parse_file
from semantic.semantic_builder import build_semantic_graph_from_ast, SemanticGraph
from analysis_reports import generate_ast_report, generate_semantic_report


class AnalysisPipeline:
    """Analysis pipeline for source code: AST -> Semantic"""
    
    SUPPORTED_LANGUAGES = ["python", "javascript", "typescript", "tsx"]
    
    EXTENSION_MAP = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'tsx'
    }
    
    def __init__(self, language: Optional[str] = None):
        """
        Initialize pipeline for a specific language.
        
        Args:
            language: Source language (python, javascript, typescript, tsx)
                     If None, language will be auto-detected from file extension
        """
        if language is not None and language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}. Choose from {self.SUPPORTED_LANGUAGES}")
        
        self.language = language
        self.ast_tree = None
        self.semantic = None
        self.source_code: Optional[bytes] = None
        self.source_path: Optional[Path] = None
        
        # Reports
        self.ast_report: Optional[Dict[str, Any]] = None
        self.semantic_report: Optional[Dict[str, Any]] = None
        self.report_paths: Dict[str, str] = {}
    
    @staticmethod
    def detect_language_from_file(file_path: str) -> str:
        """Auto-detect language from file extension."""
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension not in AnalysisPipeline.EXTENSION_MAP:
            raise ValueError(
                f"Unsupported file extension: {extension}. "
                f"Supported: {', '.join(AnalysisPipeline.EXTENSION_MAP.keys())}"
            )
        
        return AnalysisPipeline.EXTENSION_MAP[extension]
    
    def parse_code(self, code: Union[str, bytes], language: Optional[str] = None) -> Any:
        """
        Parse source code into AST.
        
        Args:
            code: Source code string or bytes
            language: Language to parse (overrides pipeline language if provided)
        
        Returns:
            AST tree object
        """
        lang = language or self.language
        if lang is None:
            raise ValueError(
                "No language specified. Either provide language parameter or "
                "initialize pipeline with a language, or use parse_file() for auto-detection."
            )
        
        self.language = lang
        
        if isinstance(code, str):
            self.source_code = code.encode('utf-8')
        else:
            self.source_code = code
        
        self.source_path = None
        self.ast_tree = parse_code(code, lang)
        return self.ast_tree
    
    def parse_file(self, file_path: str, language: Optional[str] = None) -> Any:
        """
        Parse a source file into AST. Auto-detects language from file extension if not specified.
        
        Args:
            file_path: Path to source file (.py, .js, .jsx, .ts, .tsx)
            language: Language override (if None, auto-detects from extension)
        
        Returns:
            AST tree object
        """
        if language is None and self.language is None:
            self.language = self.detect_language_from_file(file_path)
        elif language is not None:
            self.language = language
        
        assert self.language is not None, "Language must be set"
        
        with open(file_path, 'rb') as f:
            self.source_code = f.read()
        
        self.source_path = Path(file_path)
        self.ast_tree = parse_file(file_path, self.language)
        return self.ast_tree
    
    def build_semantic(self) -> SemanticGraph:
        """
        Build Semantic Graph from AST.
        
        Returns:
            SemanticGraph object
        """
        if self.ast_tree is None:
            raise ValueError("No AST available. Call parse_code() or parse_file() first.")
        
        assert self.language is not None, "Language must be set before building Semantic Graph"
        self.semantic = build_semantic_graph_from_ast(
            self.ast_tree.root_node, 
            self.language, 
            self.source_code
        )
        return self.semantic
    
    def generate_reports(self):
        """Generate AST and Semantic reports."""
        language = self.language or "python"
        
        if self.ast_tree is not None:
            self.ast_report = generate_ast_report(self.ast_tree, self.source_code, language)
        else:
            self.ast_report = None
        
        if self.semantic is not None:
            self.semantic_report = generate_semantic_report(self.semantic)
        else:
            self.semantic_report = None
    
    def export_reports(self, output_dir: Union[str, Path], base_name: Optional[str] = None) -> Dict[str, str]:
        """Write reports to disk and return their paths."""
        if not any([self.ast_report, self.semantic_report]):
            return {}
        
        if base_name is None:
            base_name = self.source_path.stem if self.source_path else "analysis"
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        reports = {"ast": self.ast_report, "semantic": self.semantic_report}
        stored_paths: Dict[str, str] = {}
        
        for key, payload in reports.items():
            if not payload:
                continue
            file_path = output_path / f"{base_name}_{key}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)
            stored_paths[key] = str(file_path)
        
        self.report_paths = stored_paths
        return stored_paths
    
    def run_full_pipeline(self, code: str) -> Dict[str, Any]:
        """
        Run the complete pipeline: AST -> Semantic
        
        Args:
            code: Source code string
        
        Returns:
            Dictionary containing all analysis results
        """
        self.parse_code(code)
        self.build_semantic()
        self.generate_reports()
        return self.get_results()
    
    def run_pipeline_on_file(self, file_path: str, output_dir: Union[str, Path] = "output") -> Dict[str, Any]:
        """
        Run the complete pipeline on a file: AST -> Semantic
        
        Args:
            file_path: Path to source file
            output_dir: Directory to save reports
        
        Returns:
            Dictionary containing all analysis results
        """
        self.parse_file(file_path)
        self.build_semantic()
        self.generate_reports()
        
        if output_dir:
            self.export_reports(output_dir, Path(file_path).stem)
        
        return self.get_results()
    
    def get_results(self) -> Dict[str, Any]:
        """Get all analysis results."""
        results = {
            "language": self.language,
            "ast": None,
            "semantic": None,
            "ast_report": self.ast_report,
            "semantic_report": self.semantic_report,
            "report_paths": self.report_paths,
        }
        
        if self.ast_tree:
            root_node = self.ast_tree.root_node
            root_text = getattr(root_node, "text", b"").decode("utf-8", errors="replace")
            results["ast"] = {
                "root_type": root_node.type,
                "root_text": root_text[:200] + ("..." if len(root_text) > 200 else ""),
                "num_children": len(root_node.children),
            }
        
        if self.semantic:
            results["semantic"] = self.semantic.to_dict()
        
        return results
    
    def export_to_json(self, output_path: str):
        """Export all results to JSON file."""
        results = self.get_results()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"Results exported to {output_path}")
    
    def export_visualizations(self, output_dir: str):
        """Export DOT visualization for Semantic Graph."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if self.semantic:
            semantic_dot = self.semantic.to_dot()
            semantic_path = output_path / "semantic.dot"
            with open(semantic_path, 'w', encoding='utf-8') as f:
                f.write(semantic_dot)
            print(f"Semantic Graph saved to {semantic_path}")
    
    def print_summary(self):
        """Print a summary of the analysis."""
        print("=" * 60)
        print("ANALYSIS PIPELINE SUMMARY")
        print("=" * 60)
        print(f"Language: {self.language}")
        
        if self.ast_tree:
            print(f"\nAST:")
            print(f"  Root type: {self.ast_tree.root_node.type}")
            print(f"  Children: {len(self.ast_tree.root_node.children)}")
        
        if self.semantic:
            print(f"\nSemantic Graph:")
            print(f"  Nodes: {len(self.semantic.nodes)}")
            print(f"  Edges: {len(self.semantic.edges)}")
            print(f"  Functions: {len(self.semantic.find_nodes_by_type('function'))}")
            print(f"  Classes: {len(self.semantic.find_nodes_by_type('class'))}")
            print(f"  Variables: {len(self.semantic.find_nodes_by_type('variable'))}")
        
        print("=" * 60)


def analyze_code(code: str, language: str = "python") -> Dict[str, Any]:
    """Convenience function to analyze code and get all results."""
    pipeline = AnalysisPipeline(language)
    return pipeline.run_full_pipeline(code)


def analyze_file(file_path: str, language: Optional[str] = None, output_dir: Union[str, Path] = "output") -> Dict[str, Any]:
    """Convenience function to analyze a file."""
    if language is None:
        ext = Path(file_path).suffix.lower()
        language = AnalysisPipeline.EXTENSION_MAP.get(ext, 'python')
    
    pipeline = AnalysisPipeline(language)
    return pipeline.run_pipeline_on_file(file_path, output_dir=output_dir)


if __name__ == "__main__":
    print("Running Analysis Pipeline (AST + Semantic)\n")
    
    python_code = """
def calculate_sum(n):
    total = 0
    for i in range(n):
        if i % 2 == 0:
            total += i
    return total

result = calculate_sum(10)
print(result)
"""
    
    pipeline = AnalysisPipeline("python")
    pipeline.run_full_pipeline(python_code)
    pipeline.print_summary()
    pipeline.export_visualizations("./output")
    pipeline.export_to_json("./output/analysis.json")
