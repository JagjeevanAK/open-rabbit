"""
Complete Pipeline: AST -> CFG -> PDG
Orchestrates the complete analysis pipeline
"""

import json
from typing import Dict, Optional, Tuple, Any, Union
from pathlib import Path
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

from cfg.cfg_builder import build_cfg_from_ast, ControlFlowGraph
from pdg.pdg_builder import build_pdg_from_cfg, ProgramDependenceGraph


class AnalysisPipeline:
    """Complete analysis pipeline for source code"""
    
    # Language setup
    LANGUAGES = {
        "python": Language(tspython.language()),
        "javascript": Language(tsjavascript.language()),
        "typescript": Language(tstypescript.language_typescript()),
        "tsx": Language(tstypescript.language_tsx()),
    }
    
    def __init__(self, language: str = "python"):
        """
        Initialize pipeline for a specific language
        
        Args:
            language: Source language (python, javascript, typescript, tsx)
        """
        if language not in self.LANGUAGES:
            raise ValueError(f"Unsupported language: {language}. Choose from {list(self.LANGUAGES.keys())}")
        
        self.language = language
        self.parser = Parser(self.LANGUAGES[language])
        self.ast_tree = None
        self.cfg = None
        self.pdg = None
    
    def parse_code(self, code: Union[str, bytes]) -> Any:
        """
        Parse source code into AST
        
        Args:
            code: Source code string or bytes
        
        Returns:
            AST tree object
        """
        if isinstance(code, str):
            source_code = code.encode('utf-8')
        else:
            source_code = code
        
        self.ast_tree = self.parser.parse(source_code)
        return self.ast_tree
    
    def parse_file(self, file_path: str) -> Any:
        """
        Parse a source file into AST
        
        Args:
            file_path: Path to source file
        
        Returns:
            AST tree object
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        return self.parse_code(code)
    
    def build_cfg(self) -> ControlFlowGraph:
        """
        Build Control Flow Graph from parsed AST
        
        Returns:
            CFG object
        """
        if self.ast_tree is None:
            raise ValueError("No AST available. Call parse_code() or parse_file() first.")
        
        self.cfg = build_cfg_from_ast(self.ast_tree.root_node, self.language)
        return self.cfg
    
    def build_pdg(self) -> ProgramDependenceGraph:
        """
        Build Program Dependence Graph from CFG
        
        Returns:
            PDG object
        """
        if self.cfg is None:
            raise ValueError("No CFG available. Call build_cfg() first.")
        
        self.pdg = build_pdg_from_cfg(self.cfg, self.language)
        return self.pdg
    
    def run_full_pipeline(self, code: str) -> Dict[str, Any]:
        """
        Run the complete pipeline: AST -> CFG -> PDG
        
        Args:
            code: Source code string
        
        Returns:
            Dictionary containing all analysis results
        """
        # Parse
        self.parse_code(code)
        
        # Build CFG
        self.build_cfg()
        
        # Build PDG
        self.build_pdg()
        
        return self.get_results()
    
    def run_pipeline_on_file(self, file_path: str) -> Dict[str, Any]:
        """
        Run the complete pipeline on a file
        
        Args:
            file_path: Path to source file
        
        Returns:
            Dictionary containing all analysis results
        """
        # Parse
        self.parse_file(file_path)
        
        # Build CFG
        self.build_cfg()
        
        # Build PDG
        self.build_pdg()
        
        return self.get_results()
    
    def get_results(self) -> Dict[str, Any]:
        """
        Get all analysis results
        
        Returns:
            Dictionary with AST, CFG, and PDG information
        """
        results = {
            "language": self.language,
            "ast": None,
            "cfg": None,
            "pdg": None,
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
        Export DOT visualizations for CFG and PDG
        
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


def analyze_file(file_path: str, language: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to analyze a file
    
    Args:
        file_path: Path to source file
        language: Programming language (auto-detected if None)
    
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
    return pipeline.run_pipeline_on_file(file_path)


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
