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

class AnalysisPipeline:
    """Complete analysis pipeline for source code: AST -> CFG -> PDG"""
    
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
        # Pass AST root node to CFG builder
        self.cfg = build_cfg_from_ast(self.ast_tree.root_node, self.language)
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
    
    def run_full_pipeline(self, code: str) -> Dict[str, Any]:
        """
        Run the complete pipeline: AST -> CFG -> PDG
        
        Pipeline Flow:
        1. AST: Parse code using ast_module
        2. CFG: Build control flow graph from AST
        3. PDG: Build program dependence graph from CFG
        
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
        
        return self.get_results()
    
    def run_pipeline_on_file(self, file_path: str) -> Dict[str, Any]:
        """
        Run the complete pipeline on a file: AST -> CFG -> PDG
        
        Pipeline Flow:
        1. AST: Parse file using ast_module
        2. CFG: Build control flow graph from AST
        3. PDG: Build program dependence graph from CFG
        
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
