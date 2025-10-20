"""
Complete Pipeline: AST -> CFG -> PDG
Orchestrates the complete analysis pipeline
"""

import json
from typing import Dict, Optional, Any, Union
from pathlib import Path

# Import from separate modules for clean separation of concerns
from ast_module.ast_parser import parse_code, parse_file
from cfg.cfg_builder import build_cfg_from_ast, ControlFlowGraph
from pdg.pdg_builder import build_pdg_from_cfg, ProgramDependenceGraph
from semantic.semantic_builder import build_semantic_graph_from_ast, SemanticGraph
from analysis_reports import (
    generate_ast_report,
    generate_cfg_report,
    generate_pdg_report,
    generate_semantic_report,
)

class AnalysisPipeline:
    """Complete analysis pipeline for source code: AST -> CFG -> PDG -> Semantic"""
    
    SUPPORTED_LANGUAGES = ["python", "javascript", "typescript", "tsx"]
    
    # File extension to language mapping
    EXTENSION_MAP = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',  # JSX is parsed as JavaScript
        '.ts': 'typescript',
        '.tsx': 'tsx'
    }
    
    def __init__(self, language: Optional[str] = None):
        """
        Initialize pipeline for a specific language
        
        Args:
            language: Source language (python, javascript, typescript, tsx)
                     If None, language will be auto-detected from file extension
        """
        if language is not None and language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}. Choose from {self.SUPPORTED_LANGUAGES}")
        
        self.language = language
        self.ast_tree = None
        self.cfg = None
        self.pdg = None
        self.semantic = None
        self.source_code: Optional[bytes] = None  # Store source code for CFG/PDG
        self.source_path: Optional[Path] = None

        # Focused reports
        self.ast_report: Optional[Dict[str, Any]] = None
        self.cfg_report: Optional[Dict[str, Any]] = None
        self.pdg_report: Optional[Dict[str, Any]] = None
        self.semantic_report: Optional[Dict[str, Any]] = None
        self.report_paths: Dict[str, str] = {}
    
    @staticmethod
    def detect_language_from_file(file_path: str) -> str:
        """
        Auto-detect language from file extension
        
        Args:
            file_path: Path to the file
            
        Returns:
            Detected language (python, javascript, typescript, tsx)
            
        Raises:
            ValueError: If file extension is not supported
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension not in AnalysisPipeline.EXTENSION_MAP:
            raise ValueError(
                f"Unsupported file extension: {extension}. "
                f"Supported extensions: {', '.join(AnalysisPipeline.EXTENSION_MAP.keys())}"
            )
        
        return AnalysisPipeline.EXTENSION_MAP[extension]
    
    def parse_code(self, code: Union[str, bytes], language: Optional[str] = None) -> Any:
        """
        Step 1: Parse source code into AST using ast_module
        
        Args:
            code: Source code string or bytes
            language: Language to parse (overrides pipeline language if provided)
        
        Returns:
            AST tree object
            
        Raises:
            ValueError: If no language is specified and pipeline has no language
        """
        lang = language or self.language
        if lang is None:
            raise ValueError(
                "No language specified. Either provide language parameter or "
                "initialize pipeline with a language, or use parse_file() for auto-detection."
            )
        
        self.language = lang  # Update pipeline language
        
        # Store source code
        if isinstance(code, str):
            self.source_code = code.encode('utf-8')
        else:
            self.source_code = code
        
        self.source_path = None
        self.ast_tree = parse_code(code, lang)
        return self.ast_tree
    
    def parse_file(self, file_path: str, language: Optional[str] = None) -> Any:
        """
        Step 1: Parse a source file into AST using ast_module
        Auto-detects language from file extension if not specified.
        
        Args:
            file_path: Path to source file (.py, .js, .jsx, .ts, .tsx)
            language: Language override (if None, auto-detects from extension)
        
        Returns:
            AST tree object
            
        Examples:
            >>> pipeline = AnalysisPipeline()
            >>> pipeline.parse_file("script.py")  # Auto-detects Python
            >>> pipeline.parse_file("app.tsx")     # Auto-detects TSX
        """
        # Auto-detect language from file extension if not specified
        if language is None and self.language is None:
            self.language = self.detect_language_from_file(file_path)
        elif language is not None:
            self.language = language
        
        assert self.language is not None, "Language must be set"
        
        # Read source code
        with open(file_path, 'rb') as f:
            self.source_code = f.read()
        
        self.source_path = Path(file_path)
        self.ast_tree = parse_file(file_path, self.language)
        return self.ast_tree
    
    def build_cfg(self) -> ControlFlowGraph:
        """
        Step 2: Build Control Flow Graph from parsed AST
        
        Takes the AST output and creates a CFG showing program flow
        
        Returns:
            CFG object
        """
        if self.ast_tree is None:
            raise ValueError("No AST available. Call parse_code() or parse_file() first.")
        
        assert self.language is not None, "Language must be set before building CFG"
        # Pass AST root node and source code to CFG builder
        self.cfg = build_cfg_from_ast(self.ast_tree.root_node, self.language, self.source_code)
        return self.cfg
    
    def build_pdg(self) -> ProgramDependenceGraph:
        """
        Step 3: Build Program Dependence Graph from CFG
        
        Takes the CFG output and creates a PDG tracking data and control dependencies
        
        Returns:
            PDG object
        """
        if self.cfg is None:
            raise ValueError("No CFG available. Call build_cfg() first.")
        
        assert self.language is not None, "Language must be set before building PDG"
        # Pass CFG to PDG builder
        self.pdg = build_pdg_from_cfg(self.cfg, self.language)
        return self.pdg
    
    def build_semantic(self) -> SemanticGraph:
        """
        Step 4: Build Semantic Graph from AST
        
        Takes the AST output and creates a semantic knowledge graph
        
        Returns:
            SemanticGraph object
        """
        if self.ast_tree is None:
            raise ValueError("No AST available. Call parse_code() or parse_file() first.")
        
        assert self.language is not None, "Language must be set before building Semantic Graph"
        # Pass AST root node and source code to Semantic builder
        self.semantic = build_semantic_graph_from_ast(self.ast_tree.root_node, self.language, self.source_code)
        return self.semantic

    def generate_component_reports(self):
        """Generate focused reports for AST, CFG, PDG, and Semantic."""
        language = self.language or "python"
        self.report_paths = {}

        if self.ast_tree is not None:
            self.ast_report = generate_ast_report(self.ast_tree, self.source_code, language)
        else:
            self.ast_report = None

        if self.cfg is not None:
            self.cfg_report = generate_cfg_report(self.cfg)
        else:
            self.cfg_report = None

        if self.pdg is not None:
            self.pdg_report = generate_pdg_report(self.pdg)
        else:
            self.pdg_report = None
        
        if self.semantic is not None:
            self.semantic_report = generate_semantic_report(self.semantic)
        else:
            self.semantic_report = None

    def export_component_reports(self, output_dir: Union[str, Path], base_name: Optional[str] = None) -> Dict[str, str]:
        """Write focused component reports to disk and return their paths."""
        if not any([self.ast_report, self.cfg_report, self.pdg_report, self.semantic_report]):
            return {}

        if base_name is None:
            if self.source_path is not None:
                base_name = self.source_path.stem
            else:
                base_name = "analysis"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        reports = {
            "ast": self.ast_report,
            "cfg": self.cfg_report,
            "pdg": self.pdg_report,
            "semantic": self.semantic_report,
        }

        stored_paths: Dict[str, str] = {}
        for key, payload in reports.items():
            if not payload:
                continue
            file_path = output_path / f"{base_name}_{key}.json"
            with open(file_path, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, indent=2)
            stored_paths[key] = str(file_path)

        self.report_paths = stored_paths
        return stored_paths
    
    def run_full_pipeline(self, code: str) -> Dict[str, Any]:
        """
        Run the complete pipeline: AST -> CFG -> PDG -> Semantic
        
        Pipeline Flow:
        1. AST: Parse code using ast_module
        2. CFG: Build control flow graph from AST
        3. PDG: Build program dependence graph from CFG
        4. Semantic: Build semantic knowledge graph from AST
        
        Args:
            code: Source code string
        
        Returns:
            Dictionary containing all analysis results
        """
        # Step 1: Parse code to AST
        self.parse_code(code)
        
        # Step 2: Build CFG from AST
        self.build_cfg()
        
        # Step 3: Build PDG from CFG
        self.build_pdg()
        
        # Step 4: Build Semantic Graph from AST
        self.build_semantic()

        # Focused summaries
        self.generate_component_reports()
        
        return self.get_results()
    
    def run_pipeline_on_file(self, file_path: str, output_dir: Union[str, Path] = "output") -> Dict[str, Any]:
        """
        Run the complete pipeline on a file: AST -> CFG -> PDG -> Semantic
        
        Pipeline Flow:
        1. AST: Parse file using ast_module
        2. CFG: Build control flow graph from AST
        3. PDG: Build program dependence graph from CFG
        4. Semantic: Build semantic knowledge graph from AST
        
        Args:
            file_path: Path to source file
        
        Returns:
            Dictionary containing all analysis results
        """
        # Step 1: Parse file to AST
        self.parse_file(file_path)
        
        # Step 2: Build CFG from AST
        self.build_cfg()
        
        # Step 3: Build PDG from CFG
        self.build_pdg()
        
        # Step 4: Build Semantic Graph from AST
        self.build_semantic()

        # Focused summaries
        self.generate_component_reports()

        # Persist dedicated outputs
        if output_dir:
            self.export_component_reports(output_dir, Path(file_path).stem)
        
        return self.get_results()
    
    def get_results(self) -> Dict[str, Any]:
        """
        Get all analysis results
        
        Returns:
            Dictionary with AST, CFG, PDG, and Semantic information
        """
        results = {
            "language": self.language,
            "ast": None,
            "cfg": None,
            "pdg": None,
            "semantic": None,
            "ast_report": self.ast_report,
            "cfg_report": self.cfg_report,
            "pdg_report": self.pdg_report,
            "semantic_report": self.semantic_report,
            "report_paths": self.report_paths,
        }
        
        if self.ast_tree:
            root_node = self.ast_tree.root_node
            root_text_bytes = getattr(root_node, "text", None)
            if root_text_bytes:
                root_text = root_text_bytes.decode("utf-8", errors="replace")
                root_preview = root_text[:200] + ("..." if len(root_text) > 200 else "")
            else:
                root_preview = ""
            results["ast"] = {
                "root_type": root_node.type,
                "root_text": root_preview,
                "num_children": len(root_node.children),
            }
        
        if self.cfg:
            results["cfg"] = self.cfg.to_dict()
        
        if self.pdg:
            results["pdg"] = self.pdg.to_dict()
        
        if self.semantic:
            results["semantic"] = self.semantic.to_dict()
        
        return results
    
    def export_to_json(self, output_path: str):
        """
        Export all results to JSON file
        
        Args:
            output_path: Path to output JSON file
        """
        results = self.get_results()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        
        print(f"Results exported to {output_path}")
    
    def export_visualizations(self, output_dir: str):
        """
        Export DOT visualizations for CFG, PDG, and Semantic Graph
        
        Args:
            output_dir: Directory to save visualization files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if self.cfg:
            cfg_dot = self.cfg.to_dot()
            cfg_path = output_path / "cfg.dot"
            with open(cfg_path, 'w', encoding='utf-8') as f:
                f.write(cfg_dot)
            print(f"CFG visualization saved to {cfg_path}")
        
        if self.pdg:
            pdg_dot = self.pdg.to_dot()
            pdg_path = output_path / "pdg.dot"
            with open(pdg_path, 'w', encoding='utf-8') as f:
                f.write(pdg_dot)
            print(f"PDG visualization saved to {pdg_path}")
        
        if self.semantic:
            semantic_dot = self.semantic.to_dot()
            semantic_path = output_path / "semantic.dot"
            with open(semantic_path, 'w', encoding='utf-8') as f:
                f.write(semantic_dot)
            print(f"Semantic Graph visualization saved to {semantic_path}")
    
    def print_summary(self):
        """Print a summary of the analysis"""
        print("=" * 60)
        print("ANALYSIS PIPELINE SUMMARY")
        print("=" * 60)
        print(f"Language: {self.language}")
        
        if self.ast_tree:
            print(f"\nAST:")
            print(f"  Root type: {self.ast_tree.root_node.type}")
            print(f"  Children: {len(self.ast_tree.root_node.children)}")
        
        if self.cfg:
            print(f"\nCFG:")
            print(f"  Blocks: {len(self.cfg.blocks)}")
            print(f"  Entry: {self.cfg.entry_block_id}")
            print(f"  Exit: {self.cfg.exit_block_id}")
        
        if self.pdg:
            print(f"\nPDG:")
            print(f"  Nodes: {len(self.pdg.nodes)}")
            print(f"  Variables: {len(self.pdg.variables)}")
            
            # Count dependencies
            total_data_deps = sum(len(node.data_dependencies) for node in self.pdg.nodes.values())
            total_ctrl_deps = sum(len(node.control_dependencies) for node in self.pdg.nodes.values())
            print(f"  Data dependencies: {total_data_deps}")
            print(f"  Control dependencies: {total_ctrl_deps}")
        
        if self.semantic:
            print(f"\nSemantic Graph:")
            print(f"  Nodes: {len(self.semantic.nodes)}")
            print(f"  Edges: {len(self.semantic.edges)}")
            print(f"  Functions: {len(self.semantic.find_nodes_by_type('function'))}")
            print(f"  Classes: {len(self.semantic.find_nodes_by_type('class'))}")
            print(f"  Variables: {len(self.semantic.find_nodes_by_type('variable'))}")
        
        print("=" * 60)


def analyze_code(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Convenience function to analyze code and get all results
    
    Args:
        code: Source code string
        language: Programming language
    
    Returns:
        Dictionary with all analysis results
    """
    pipeline = AnalysisPipeline(language)
    return pipeline.run_full_pipeline(code)


def analyze_file(
    file_path: str,
    language: Optional[str] = None,
    output_dir: Union[str, Path] = "output",
) -> Dict[str, Any]:
    """
    Convenience function to analyze a file
    
    Args:
    file_path: Path to source file
    language: Programming language (auto-detected if None)
    output_dir: Directory where focused reports should be written
    
    Returns:
        Dictionary with all analysis results
    """
    # Auto-detect language from extension
    if language is None:
        ext = Path(file_path).suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'tsx',
        }
        language = language_map.get(ext, 'python')
    
    pipeline = AnalysisPipeline(language)
    return pipeline.run_pipeline_on_file(file_path, output_dir=output_dir)


if __name__ == "__main__":
    # Example usage
    print("Running Analysis Pipeline Example\n")
    
    # Example 1: Analyze Python code
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
    
    print("Example 1: Python Code Analysis")
    print("-" * 60)
    pipeline = AnalysisPipeline("python")
    pipeline.run_full_pipeline(python_code)
    pipeline.print_summary()
    
    # Export visualizations
    pipeline.export_visualizations("./output")
    
    # Export JSON
    pipeline.export_to_json("./output/analysis.json")
    
    print("\n" + "=" * 60)
    print("\nExample 2: JavaScript Code Analysis")
    print("-" * 60)
    
    js_code = """
function fibonacci(n) {
    if (n <= 1) {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

const result = fibonacci(10);
console.log(result);
"""
    
    pipeline_js = AnalysisPipeline("javascript")
    pipeline_js.run_full_pipeline(js_code)
    pipeline_js.print_summary()
    
    print("\n" + "=" * 60)
    print("\nVisualization files created:")
    print("  - output/cfg.dot (Control Flow Graph)")
    print("  - output/pdg.dot (Program Dependence Graph)")
    print("\nTo visualize, use Graphviz:")
    print("  dot -Tpng output/cfg.dot -o cfg.png")
    print("  dot -Tpng output/pdg.dot -o pdg.png")
