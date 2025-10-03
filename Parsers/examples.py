"""
Examples: Using the AST -> CFG -> PDG Pipeline

This file demonstrates all features of the code analysis pipeline.
Perfect for feeding to AI for code review and error detection.
"""

from pipeline import AnalysisPipeline
import json

print("=" * 80)
print("CODE ANALYSIS PIPELINE - COMPREHENSIVE EXAMPLES")
print("=" * 80)


# =============================================================================
# EXAMPLE 1: Basic Usage - Simple Code Analysis
# =============================================================================
print("\n" + "=" * 80)
print("EXAMPLE 1: Basic Usage")
print("=" * 80)

code = """
def add(a, b):
    return a + b

result = add(5, 3)
print(result)
"""

print("\nCode to analyze:")
print(code)

# Create pipeline
pipeline = AnalysisPipeline("python")

# Run complete analysis
results = pipeline.run_full_pipeline(code)

print("\nResults:")
print(f"  Language: {results['language']}")
print(f"  AST Root: {results['ast']['root_type']}")
print(f"  CFG Blocks: {len(results['cfg']['blocks'])}")
print(f"  PDG Nodes: {len(results['pdg']['nodes'])}")
print(f"  Variables: {len(results['pdg']['variables'])}")


# =============================================================================
# EXAMPLE 2: Step-by-Step Analysis
# =============================================================================
print("\n" + "=" * 80)
print("EXAMPLE 2: Step-by-Step Analysis")
print("=" * 80)

code2 = """
x = 10
y = 20
if x > y:
    z = x + y
else:
    z = x * y
result = z
"""

pipeline2 = AnalysisPipeline("python")

# Step 1: Parse to AST
print("\nStep 1: Parse to AST")
ast_tree = pipeline2.parse_code(code2)
print(f"  ✓ AST created: {ast_tree.root_node.type}")
print(f"  Children: {len(ast_tree.root_node.children)}")

# Step 2: Build CFG
print("\nStep 2: Build Control Flow Graph")
cfg = pipeline2.build_cfg()
print(f"  ✓ CFG created with {len(cfg.blocks)} blocks")
print(f"  Entry: Block {cfg.entry_block_id} -> Exit: Block {cfg.exit_block_id}")

# Show CFG structure
print("\n  Control Flow:")
for block_id, block in cfg.blocks.items():
    if block.successors:
        print(f"    Block {block_id} ({block.type.value}) -> {block.successors}")

# Step 3: Build PDG
print("\nStep 3: Build Program Dependence Graph")
pdg = pipeline2.build_pdg()
print(f"  ✓ PDG created with {len(pdg.nodes)} nodes")
print(f"  Variables tracked: {len(pdg.variables)}")

# Show variable dependencies
print("\n  Variable Dependencies:")
for var_name, var_info in pdg.variables.items():
    print(f"    {var_name}:")
    print(f"      Definitions at nodes: {var_info.definition_nodes}")
    print(f"      Uses at nodes: {var_info.use_nodes}")


# =============================================================================
# EXAMPLE 3: Analyzing a File
# =============================================================================
print("\n" + "=" * 80)
print("EXAMPLE 3: Analyzing a File")
print("=" * 80)

# Create a sample file
sample_file = "/tmp/sample_code.py"
with open(sample_file, "w") as f:
    f.write("""
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

result = factorial(5)
""")

print(f"\nAnalyzing file: {sample_file}")

pipeline3 = AnalysisPipeline("python")
file_results = pipeline3.run_pipeline_on_file(sample_file)

print(f"\nFile Analysis Results:")
print(f"  CFG Blocks: {len(file_results['cfg']['blocks'])}")
print(f"  PDG Nodes: {len(file_results['pdg']['nodes'])}")
print(f"  Variables: {len(file_results['pdg']['variables'])}")


# =============================================================================
# EXAMPLE 4: Multi-Language Support
# =============================================================================
print("\n" + "=" * 80)
print("EXAMPLE 4: Multi-Language Support")
print("=" * 80)

# Python
print("\n--- Python ---")
python_code = "x = 5\ny = x * 2"
py_pipeline = AnalysisPipeline("python")
py_results = py_pipeline.run_full_pipeline(python_code)
print(f"  Python: {len(py_results['cfg']['blocks'])} blocks")

# JavaScript
print("\n--- JavaScript ---")
js_code = "const x = 5;\nconst y = x * 2;"
js_pipeline = AnalysisPipeline("javascript")
js_results = js_pipeline.run_full_pipeline(js_code)
print(f"  JavaScript: {len(js_results['cfg']['blocks'])} blocks")


# =============================================================================
# EXAMPLE 5: Exporting Results for AI Analysis
# =============================================================================
print("\n" + "=" * 80)
print("EXAMPLE 5: Exporting Results for AI Analysis")
print("=" * 80)

code_for_ai = """
def process_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
        else:
            result.append(item)
    return result

values = [1, -2, 3, -4, 5]
output = process_data(values)
"""

pipeline5 = AnalysisPipeline("python")
ai_results = pipeline5.run_full_pipeline(code_for_ai)

# Export to JSON for AI consumption
output_file = "/tmp/code_analysis_for_ai.json"
pipeline5.export_to_json(output_file)
print(f"\n✓ Exported analysis to: {output_file}")

# Export visualizations
viz_dir = "/tmp/visualizations"
pipeline5.export_visualizations(viz_dir)
print(f"✓ Exported visualizations to: {viz_dir}")
print(f"  - {viz_dir}/cfg.dot (Control Flow Graph)")
print(f"  - {viz_dir}/pdg.dot (Program Dependence Graph)")

print("\nAI-Ready Data Structure:")
print(f"  AST: {ai_results['ast']['root_type']} with {ai_results['ast']['num_children']} children")
print(f"  CFG: {len(ai_results['cfg']['blocks'])} blocks")
print(f"  PDG: {len(ai_results['pdg']['nodes'])} nodes")


# =============================================================================
# EXAMPLE 6: Detailed CFG Analysis
# =============================================================================
print("\n" + "=" * 80)
print("EXAMPLE 6: Detailed CFG Analysis")
print("=" * 80)

loop_code = """
total = 0
for i in range(10):
    if i % 2 == 0:
        total += i
print(total)
"""

print("\nCode:")
print(loop_code)

pipeline6 = AnalysisPipeline("python")
pipeline6.run_full_pipeline(loop_code)

cfg = pipeline6.cfg
assert cfg is not None, "CFG not built"
print("\nCFG Analysis:")
print(f"  Total blocks: {len(cfg.blocks)}")
print(f"  Entry block: {cfg.entry_block_id}")
print(f"  Exit block: {cfg.exit_block_id}")

# Analyze block types
from collections import Counter
block_types = Counter(block.type.value for block in cfg.blocks.values())
print(f"\n  Block type distribution:")
for block_type, count in block_types.items():
    print(f"    {block_type}: {count}")

# Show reachable blocks
assert cfg.entry_block_id is not None, "No entry block"
reachable = cfg.get_reachable_blocks(cfg.entry_block_id)
print(f"\n  Reachable blocks from entry: {len(reachable)}")

# Detailed block information
print("\n  Block Details:")
for block_id, block in list(cfg.blocks.items())[:6]:  # Show first 6
    print(f"    Block {block_id} ({block.type.value}):")
    print(f"      Predecessors: {block.predecessors}")
    print(f"      Successors: {block.successors}")
    if block.statements:
        print(f"      Statements: {block.statements[:2]}")


# =============================================================================
# EXAMPLE 7: Detailed PDG Analysis (For AI Code Review)
# =============================================================================
print("\n" + "=" * 80)
print("EXAMPLE 7: Detailed PDG Analysis (For AI Code Review)")
print("=" * 80)

review_code = """
def calculate_discount(price, discount_rate):
    if discount_rate > 1:
        discount_rate = discount_rate / 100
    
    discount = price * discount_rate
    final_price = price - discount
    
    return final_price

item_price = 100
discount = 0.15
result = calculate_discount(item_price, discount)
"""

print("\nCode to review:")
print(review_code)

pipeline7 = AnalysisPipeline("python")
pipeline7.run_full_pipeline(review_code)

pdg = pipeline7.pdg
assert pdg is not None, "PDG not built"
print("\nPDG Analysis for AI Code Review:")
print(f"  Total nodes: {len(pdg.nodes)}")
print(f"  Variables tracked: {len(pdg.variables)}")

# Variable analysis
print("\n  Variable Analysis:")
for var_name, var_info in pdg.variables.items():
    print(f"\n    Variable: {var_name}")
    print(f"      Scope: {var_info.scope}")
    print(f"      Defined at nodes: {var_info.definition_nodes}")
    print(f"      Used at nodes: {var_info.use_nodes}")
    
    # Check for potential issues
    if not var_info.use_nodes:
        print(f"      ⚠️  WARNING: Variable defined but never used!")
    if not var_info.definition_nodes and var_info.use_nodes:
        print(f"      ⚠️  WARNING: Variable used but never defined!")

# Dependency analysis
print("\n  Data Dependencies:")
for node_id, node in pdg.nodes.items():
    if node.data_dependencies:
        print(f"    Node {node_id} depends on nodes: {node.data_dependencies}")
        print(f"      Uses: {node.uses}")
        print(f"      Defines: {node.defines}")

# Control dependencies
print("\n  Control Dependencies:")
for node_id, node in pdg.nodes.items():
    if node.control_dependencies:
        print(f"    Node {node_id} controlled by nodes: {node.control_dependencies}")


# =============================================================================
# EXAMPLE 8: AI-Friendly Summary Function
# =============================================================================
print("\n" + "=" * 80)
print("EXAMPLE 8: AI-Friendly Summary Function")
print("=" * 80)

def get_ai_friendly_summary(code, language="python"):
    """
    Generate a comprehensive summary for AI code review
    """
    pipeline = AnalysisPipeline(language)
    results = pipeline.run_full_pipeline(code)
    
    summary = {
        "metadata": {
            "language": language,
            "ast_type": results['ast']['root_type'],
            "num_children": results['ast']['num_children']
        },
        "control_flow": {
            "total_blocks": len(results['cfg']['blocks']),
            "entry_block": results['cfg']['entry_block'],
            "exit_block": results['cfg']['exit_block'],
            "block_types": {},
        },
        "dependencies": {
            "total_nodes": len(results['pdg']['nodes']),
            "total_variables": len(results['pdg']['variables']),
            "variables": {},
            "data_dependencies": 0,
            "control_dependencies": 0
        },
        "potential_issues": []
    }
    
    # Count block types
    for block in results['cfg']['blocks'].values():
        bt = block['type']
        summary['control_flow']['block_types'][bt] = \
            summary['control_flow']['block_types'].get(bt, 0) + 1
    
    # Analyze variables
    for var_name, var_info in results['pdg']['variables'].items():
        summary['dependencies']['variables'][var_name] = {
            'definitions': len(var_info['definitions']),
            'uses': len(var_info['uses'])
        }
        
        # Detect unused variables
        if var_info['definitions'] and not var_info['uses']:
            summary['potential_issues'].append({
                'type': 'unused_variable',
                'variable': var_name,
                'severity': 'warning'
            })
        
        # Detect undefined variables
        if var_info['uses'] and not var_info['definitions']:
            summary['potential_issues'].append({
                'type': 'undefined_variable',
                'variable': var_name,
                'severity': 'error'
            })
    
    # Count dependencies
    for node in results['pdg']['nodes'].values():
        summary['dependencies']['data_dependencies'] += len(node['data_dependencies'])
        summary['dependencies']['control_dependencies'] += len(node['control_dependencies'])
    
    return summary

# Example usage
test_code = """
def greet(name):
    message = f"Hello, {name}!"
    unused_var = 42  # This will be flagged as unused
    return message

result = greet("World")
print(result)
"""

print("\nCode:")
print(test_code)

summary = get_ai_friendly_summary(test_code)

print("\n✓ AI-Friendly Summary Generated:")
print(json.dumps(summary, indent=2))


# =============================================================================
# EXAMPLE 9: Batch Analysis
# =============================================================================
print("\n" + "=" * 80)
print("EXAMPLE 9: Batch Analysis of Multiple Code Snippets")
print("=" * 80)

code_samples = {
    "simple_function": "def add(a, b):\n    return a + b",
    "with_loop": "for i in range(5):\n    print(i)",
    "with_condition": "x = 10\nif x > 5:\n    print('big')\nelse:\n    print('small')",
}

print("\nAnalyzing multiple code snippets:")

results_summary = []
for name, code in code_samples.items():
    pipeline = AnalysisPipeline("python")
    result = pipeline.run_full_pipeline(code)
    
    results_summary.append({
        "name": name,
        "blocks": len(result['cfg']['blocks']),
        "nodes": len(result['pdg']['nodes']),
        "variables": len(result['pdg']['variables'])
    })
    
    print(f"\n  {name}:")
    print(f"    CFG Blocks: {len(result['cfg']['blocks'])}")
    print(f"    PDG Nodes: {len(result['pdg']['nodes'])}")
    print(f"    Variables: {len(result['pdg']['variables'])}")

print("\n✓ Batch analysis complete!")


# =============================================================================
# SUMMARY & BEST PRACTICES FOR AI CODE REVIEW
# =============================================================================
print("\n" + "=" * 80)
print("BEST PRACTICES FOR AI CODE REVIEW")
print("=" * 80)

print("""
1. Use run_full_pipeline() for complete analysis:
   results = pipeline.run_full_pipeline(code)

2. Export to JSON for AI consumption:
   pipeline.export_to_json("analysis.json")

3. Key data for AI code review:
   - CFG blocks: Shows program flow and complexity
   - PDG variables: Shows data dependencies and potential issues
   - Control/Data dependencies: Shows code coupling

4. Check for common issues:
   - Unused variables (definitions but no uses)
   - Undefined variables (uses but no definitions)
   - Unreachable code (blocks not in reachable set)
   - High complexity (many CFG blocks)

5. Use get_ai_friendly_summary() to generate structured data
   for AI models to analyze

6. Export visualizations for human-readable code flow:
   pipeline.export_visualizations("./output")
   
   Then convert DOT files to images:
   dot -Tpng output/cfg.dot -o cfg.png
   dot -Tpng output/pdg.dot -o pdg.png
""")

print("\n" + "=" * 80)
print("✅ ALL EXAMPLES COMPLETE!")
print("=" * 80)
print("\nThe pipeline is ready for AI-powered code review!")
print("Feed the JSON output to your AI model for comprehensive code analysis.")
