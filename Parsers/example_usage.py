"""
Example Usage of the AST -> CFG -> PDG Pipeline

This demonstrates how to use the complete analysis pipeline
"""

from pipeline import AnalysisPipeline, analyze_code, analyze_file
import json


def example_1_simple_python():
    """Example 1: Analyze simple Python code"""
    print("=" * 70)
    print("EXAMPLE 1: Simple Python Code Analysis")
    print("=" * 70)
    
    code = """
def add(a, b):
    result = a + b
    return result

x = 10
y = 20
z = add(x, y)
print(z)
"""
    
    print("Code:")
    print(code)
    print("\n" + "-" * 70)
    
    pipeline = AnalysisPipeline("python")
    results = pipeline.run_full_pipeline(code)
    pipeline.print_summary()
    
    print("\nCFG Blocks:")
    for block_id, block in results['cfg']['blocks'].items():
        print(f"  Block {block_id}: {block['type']}")
        print(f"    Successors: {block['successors']}")
        if block['statements']:
            print(f"    Statements: {block['statements'][:2]}")
    
    print("\nPDG Nodes with Dependencies:")
    for node_id, node in results['pdg']['nodes'].items():
        if node['data_dependencies'] or node['control_dependencies']:
            print(f"  Node {node_id}:")
            if node['defines']:
                print(f"    Defines: {node['defines']}")
            if node['uses']:
                print(f"    Uses: {node['uses']}")
            if node['data_dependencies']:
                print(f"    Data deps: {node['data_dependencies']}")
            if node['control_dependencies']:
                print(f"    Control deps: {node['control_dependencies']}")


def example_2_control_flow():
    """Example 2: Code with complex control flow"""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Complex Control Flow Analysis")
    print("=" * 70)
    
    code = """
def max_of_three(a, b, c):
    if a > b:
        if a > c:
            return a
        else:
            return c
    else:
        if b > c:
            return b
        else:
            return c

result = max_of_three(10, 20, 15)
"""
    
    print("Code:")
    print(code)
    print("\n" + "-" * 70)
    
    pipeline = AnalysisPipeline("python")
    pipeline.run_full_pipeline(code)
    pipeline.print_summary()
    
    # Export visualizations
    pipeline.export_visualizations("./output/example2")
    print("\n✓ Visualizations exported to ./output/example2/")


def example_3_loops():
    """Example 3: Code with loops"""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Loop Analysis")
    print("=" * 70)
    
    code = """
def fibonacci(n):
    a = 0
    b = 1
    for i in range(n):
        temp = a
        a = b
        b = temp + b
    return a

result = fibonacci(10)
"""
    
    print("Code:")
    print(code)
    print("\n" + "-" * 70)
    
    pipeline = AnalysisPipeline("python")
    results = pipeline.run_full_pipeline(code)
    pipeline.print_summary()
    
    print("\nVariable Analysis:")
    for var_name, var_info in results['pdg']['variables'].items():
        print(f"  {var_name}:")
        print(f"    Definitions at nodes: {var_info['definitions']}")
        print(f"    Uses at nodes: {var_info['uses']}")


def example_4_javascript():
    """Example 4: JavaScript code analysis"""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: JavaScript Code Analysis")
    print("=" * 70)
    
    code = """
function calculateTotal(items) {
    let total = 0;
    for (let i = 0; i < items.length; i++) {
        if (items[i].price > 0) {
            total += items[i].price;
        }
    }
    return total;
}

const items = [{price: 10}, {price: 20}, {price: -5}];
const total = calculateTotal(items);
console.log(total);
"""
    
    print("Code:")
    print(code)
    print("\n" + "-" * 70)
    
    pipeline = AnalysisPipeline("javascript")
    pipeline.run_full_pipeline(code)
    pipeline.print_summary()


def example_5_data_dependencies():
    """Example 5: Demonstrate data dependencies"""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Data Dependency Analysis")
    print("=" * 70)
    
    code = """
a = 10
b = a + 5
c = b * 2
d = a + c
result = d - b
"""
    
    print("Code:")
    print(code)
    print("\n" + "-" * 70)
    
    results = analyze_code(code, "python")
    
    print(f"Total nodes: {len(results['pdg']['nodes'])}")
    print(f"Total variables: {len(results['pdg']['variables'])}")
    
    print("\nData Dependency Chain:")
    for node_id, node in results['pdg']['nodes'].items():
        if node['defines']:
            var_name = list(node['defines'])[0]
            print(f"  {var_name} (node {node_id}):", end="")
            if node['uses']:
                print(f" uses {node['uses']}", end="")
            if node['data_dependencies']:
                print(f" <- depends on nodes {node['data_dependencies']}", end="")
            print()


def example_6_export_formats():
    """Example 6: Export to different formats"""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Export to Different Formats")
    print("=" * 70)
    
    code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

result = factorial(5)
"""
    
    pipeline = AnalysisPipeline("python")
    pipeline.run_full_pipeline(code)
    
    # Export to JSON
    pipeline.export_to_json("./output/factorial_analysis.json")
    print("✓ JSON export: ./output/factorial_analysis.json")
    
    # Export visualizations
    pipeline.export_visualizations("./output/factorial")
    print("✓ DOT files: ./output/factorial/cfg.dot, ./output/factorial/pdg.dot")
    
    print("\nTo visualize DOT files, run:")
    print("  dot -Tpng ./output/factorial/cfg.dot -o ./output/factorial/cfg.png")
    print("  dot -Tpng ./output/factorial/pdg.dot -o ./output/factorial/pdg.png")


def example_7_file_analysis():
    """Example 7: Analyze a Python file"""
    print("\n" + "=" * 70)
    print("EXAMPLE 7: Analyze Python File")
    print("=" * 70)
    
    # Create a test file
    test_code = """
class Calculator:
    def __init__(self):
        self.result = 0
    
    def add(self, x):
        self.result += x
        return self.result
    
    def multiply(self, x):
        self.result *= x
        return self.result

calc = Calculator()
calc.add(10)
calc.multiply(2)
print(calc.result)
"""
    
    # Write to file
    with open("./output/test_calculator.py", "w") as f:
        f.write(test_code)
    
    print("Analyzing file: ./output/test_calculator.py")
    
    # Analyze the file
    results = analyze_file("./output/test_calculator.py", "python")
    
    print(f"\nAST root type: {results['ast']['root_type']}")
    print(f"CFG blocks: {len(results['cfg']['blocks'])}")
    print(f"PDG nodes: {len(results['pdg']['nodes'])}")
    print(f"Variables tracked: {len(results['pdg']['variables'])}")


def main():
    """Run all examples"""
    print("\n" + "🚀 " * 35)
    print("AST -> CFG -> PDG PIPELINE EXAMPLES")
    print("🚀 " * 35 + "\n")
    
    # Run examples
    example_1_simple_python()
    example_2_control_flow()
    example_3_loops()
    example_4_javascript()
    example_5_data_dependencies()
    example_6_export_formats()
    example_7_file_analysis()
    
    print("\n" + "=" * 70)
    print("ALL EXAMPLES COMPLETED!")
    print("=" * 70)
    print("\nOutput files created in ./output/ directory")
    print("\nNext steps:")
    print("  1. Check ./output/ for JSON and DOT files")
    print("  2. Use Graphviz to visualize DOT files")
    print("  3. Integrate the pipeline into your own code")
    print("\nDocumentation:")
    print("  - cfg-builder.py: Control Flow Graph construction")
    print("  - pdg-builder.py: Program Dependence Graph construction")
    print("  - pipeline.py: Complete analysis pipeline")


if __name__ == "__main__":
    main()
