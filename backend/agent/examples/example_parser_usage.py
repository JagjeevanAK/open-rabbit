#!/usr/bin/env python3
"""
Example script demonstrating how to use the Parser tools
for code analysis in the backend agent.

Usage:
    python example_parser_usage.py
"""

import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.tools.Parsers import (
    parse_code_file,
    parse_code_snippet,
    analyze_changed_files,
    get_parser_capabilities
)


def example_1_capabilities():
    """Example 1: Check parser capabilities"""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Get Parser Capabilities")
    print("=" * 70 + "\n")
    
    result = get_parser_capabilities.invoke({})
    data = json.loads(result)
    
    print("Supported Languages:", data["supported_languages"])
    print("File Extensions:", data["file_extensions"])
    print("Analysis Types:", data["analysis_types"])
    print("\nFeatures:")
    for feature in data["features"]:
        print(f"  - {feature}")


def example_2_parse_snippet():
    """Example 2: Parse a Python code snippet"""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Parse Python Code Snippet")
    print("=" * 70 + "\n")
    
    code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

result = factorial(5)
print(f"Factorial of 5 is {result}")
"""
    
    print("Code to analyze:")
    print(code)
    print("\nAnalyzing...\n")
    
    result = parse_code_snippet.invoke({
        "code": code,
        "language": "python"
    })
    
    data = json.loads(result)
    
    if data.get("success"):
        print("✓ Analysis successful!")
        results = data["results"]
        
        if results.get("ast"):
            print(f"\nAST Analysis:")
            print(f"  Root Type: {results['ast']['root_type']}")
            print(f"  Children: {results['ast']['num_children']}")
        
        if results.get("cfg"):
            cfg = results["cfg"]
            print(f"\nCFG Analysis:")
            print(f"  Total Blocks: {len(cfg.get('blocks', []))}")
            print(f"  Entry Block: {cfg.get('entry_block_id')}")
            print(f"  Exit Block: {cfg.get('exit_block_id')}")
        
        if results.get("pdg"):
            pdg = results["pdg"]
            print(f"\nPDG Analysis:")
            print(f"  Total Nodes: {len(pdg.get('nodes', []))}")
            print(f"  Variables: {len(pdg.get('variables', []))}")
    else:
        print(f"✗ Analysis failed: {data.get('error')}")


def example_3_parse_file():
    """Example 3: Parse a file from the project"""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Parse File (AST Only)")
    print("=" * 70 + "\n")
    
    # Try to find and parse the knowledgeBase.py file
    kb_file = os.path.join(os.path.dirname(__file__), "knowledgeBase.py")
    
    if not os.path.exists(kb_file):
        print(f"File not found: {kb_file}")
        return
    
    print(f"Analyzing file: {kb_file}\n")
    
    result = parse_code_file.invoke({
        "file_path": kb_file,
        "analysis_type": "ast"  # Just AST for faster analysis
    })
    
    data = json.loads(result)
    
    if data.get("success"):
        print("✓ Analysis successful!")
        results = data["results"]
        
        if results.get("ast_report"):
            ast_report = results["ast_report"]
            print(f"\nAST Report Summary:")
            print(f"  Language: {ast_report.get('language', 'N/A')}")
            
            stats = ast_report.get("statistics", {})
            print(f"\nStatistics:")
            print(f"  Total Nodes: {stats.get('total_nodes', 0)}")
            print(f"  Max Depth: {stats.get('max_depth', 0)}")
            
            if "node_types" in stats:
                print(f"\nTop Node Types:")
                node_types = stats["node_types"]
                for node_type, count in sorted(node_types.items(), key=lambda x: x[1], reverse=True)[:5]:
                    print(f"    {node_type}: {count}")
    else:
        print(f"✗ Analysis failed: {data.get('error')}")


def example_4_batch_analysis():
    """Example 4: Analyze multiple files"""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Batch Analysis of Multiple Files")
    print("=" * 70 + "\n")
    
    # Create some temporary test files
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    files = []
    
    # File 1: Simple function
    file1 = os.path.join(temp_dir, "utils.py")
    with open(file1, 'w') as f:
        f.write("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
""")
    files.append(file1)
    
    # File 2: Class definition
    file2 = os.path.join(temp_dir, "calculator.py")
    with open(file2, 'w') as f:
        f.write("""
class Calculator:
    def __init__(self):
        self.result = 0
    
    def add(self, x):
        self.result += x
        return self.result
    
    def reset(self):
        self.result = 0
""")
    files.append(file2)
    
    print(f"Created {len(files)} test files in {temp_dir}\n")
    
    result = analyze_changed_files.invoke({
        "file_paths": files
    })
    
    data = json.loads(result)
    
    print(f"Success: {data.get('success', False)}")
    print(f"Analyzed Files: {data.get('analyzed_files', 0)}")
    print(f"Errors: {len(data.get('errors', []))}")
    
    if data.get("results"):
        print("\nFile Analysis Summary:")
        for file_path, file_result in data["results"].items():
            print(f"\n  {os.path.basename(file_path)}:")
            if file_result.get("success"):
                results = file_result.get("results", {})
                if results.get("ast"):
                    print(f"    AST Root: {results['ast']['root_type']}")
                    print(f"    Children: {results['ast']['num_children']}")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


def example_5_javascript():
    """Example 5: Parse JavaScript code"""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Parse JavaScript Code")
    print("=" * 70 + "\n")
    
    js_code = """
function fibonacci(n) {
    if (n <= 1) return n;
    
    let a = 0, b = 1;
    for (let i = 2; i <= n; i++) {
        let temp = a + b;
        a = b;
        b = temp;
    }
    return b;
}

const result = fibonacci(10);
console.log(`Fibonacci(10) = ${result}`);
"""
    
    print("JavaScript code to analyze:")
    print(js_code)
    print("\nAnalyzing...\n")
    
    result = parse_code_snippet.invoke({
        "code": js_code,
        "language": "javascript"
    })
    
    data = json.loads(result)
    
    if data.get("success"):
        print("✓ Analysis successful!")
        print(f"Language: {data.get('language')}")
        
        results = data["results"]
        if results.get("cfg_report"):
            cfg_report = results["cfg_report"]
            print(f"\nCFG Summary:")
            print(f"  Total Blocks: {cfg_report.get('total_blocks', 0)}")
            print(f"  Total Edges: {cfg_report.get('total_edges', 0)}")
    else:
        print(f"✗ Analysis failed: {data.get('error')}")


def main():
    """Run all examples"""
    print("\n" + "=" * 70)
    print("PARSER TOOLS - USAGE EXAMPLES")
    print("=" * 70)
    
    try:
        example_1_capabilities()
        example_2_parse_snippet()
        example_3_parse_file()
        example_4_batch_analysis()
        example_5_javascript()
        
        print("\n" + "=" * 70)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
