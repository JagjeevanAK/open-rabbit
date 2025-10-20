"""
Example demonstrating Semantic Graph Parser usage
"""

from pathlib import Path
import sys
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import AnalysisPipeline

def main():
    """Run semantic graph example"""
    
    # Example Python code with classes and functions
    python_code = """
class Animal:
    def __init__(self, name):
        self.name = name
    
    def speak(self):
        pass

class Dog(Animal):
    def __init__(self, name, breed):
        super().__init__(name)
        self.breed = breed
    
    def speak(self):
        return "Woof!"
    
    def fetch(self, item):
        return f"{self.name} fetched {item}"

def create_dog(name, breed):
    dog = Dog(name, breed)
    return dog

def main():
    my_dog = create_dog("Buddy", "Golden Retriever")
    sound = my_dog.speak()
    result = my_dog.fetch("ball")
    print(sound)
    print(result)

if __name__ == "__main__":
    main()
"""
    
    print("=" * 80)
    print("SEMANTIC GRAPH PARSER EXAMPLE")
    print("=" * 80)
    print("\nAnalyzing Python code with classes and inheritance...\n")
    
    # Create pipeline
    pipeline = AnalysisPipeline(language="python")
    
    # Parse code
    print("Step 1: Parsing code to AST...")
    pipeline.parse_code(python_code)
    
    # Build semantic graph
    print("Step 2: Building Semantic Graph...")
    semantic = pipeline.build_semantic()
    
    # Print statistics
    print("\n" + "=" * 80)
    print("SEMANTIC GRAPH STATISTICS")
    print("=" * 80)
    print(f"Total Nodes: {len(semantic.nodes)}")
    print(f"Total Edges: {len(semantic.edges)}")
    print(f"Functions: {len(semantic.find_nodes_by_type('function'))}")
    print(f"Classes: {len(semantic.find_nodes_by_type('class'))}")
    print(f"Variables: {len(semantic.find_nodes_by_type('variable'))}")
    
    # Show functions
    print("\n" + "-" * 80)
    print("FUNCTIONS")
    print("-" * 80)
    for node in semantic.find_nodes_by_type('function'):
        print(f"  - {node.name}")
        if node.signature:
            print(f"    Signature: {node.signature}")
        if node.start_line:
            print(f"    Lines: {node.start_line}-{node.end_line}")
    
    # Show classes
    print("\n" + "-" * 80)
    print("CLASSES")
    print("-" * 80)
    for node in semantic.find_nodes_by_type('class'):
        print(f"  - {node.name}")
        if node.start_line:
            print(f"    Lines: {node.start_line}-{node.end_line}")
    
    # Show inheritance hierarchy
    print("\n" + "-" * 80)
    print("INHERITANCE HIERARCHY")
    print("-" * 80)
    hierarchy = semantic.get_inheritance_hierarchy()
    if hierarchy:
        for child_id, parent_ids in hierarchy.items():
            child = semantic.nodes[child_id]
            parents = [semantic.nodes[p].name for p in parent_ids]
            print(f"  {child.name} inherits from: {', '.join(parents)}")
    else:
        print("  No inheritance relationships found")
    
    # Show call graph
    print("\n" + "-" * 80)
    print("CALL GRAPH")
    print("-" * 80)
    call_graph = semantic.get_call_graph()
    if call_graph:
        for caller_id, callee_ids in call_graph.items():
            caller = semantic.nodes[caller_id]
            callees = [semantic.nodes[c].name for c in callee_ids if c in semantic.nodes]
            if callees:
                print(f"  {caller.name} calls: {', '.join(callees)}")
    else:
        print("  No function calls found")
    
    # Generate semantic report
    print("\n" + "-" * 80)
    print("GENERATING SEMANTIC REPORT")
    print("-" * 80)
    pipeline.generate_component_reports()
    
    if pipeline.semantic_report:
        print(f"Functions found: {pipeline.semantic_report['summary']['function_count']}")
        print(f"Classes found: {pipeline.semantic_report['summary']['class_count']}")
        print(f"Variables found: {pipeline.semantic_report['summary']['variable_count']}")
        print(f"Call relationships: {pipeline.semantic_report['summary']['call_count']}")
        print(f"Inheritance relationships: {pipeline.semantic_report['summary']['inheritance_count']}")
    
    # Export to file
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    print("\n" + "-" * 80)
    print("EXPORTING RESULTS")
    print("-" * 80)
    
    # Export semantic graph report
    if pipeline.semantic_report:
        semantic_path = output_dir / "semantic_example_semantic.json"
        with open(semantic_path, 'w', encoding='utf-8') as f:
            json.dump(pipeline.semantic_report, f, indent=2)
        print(f"Semantic report saved to: {semantic_path}")
    
    # Export visualization
    pipeline.export_visualizations(str(output_dir))
    
    # Export full semantic graph dict
    semantic_dict_path = output_dir / "semantic_example_full.json"
    with open(semantic_dict_path, 'w', encoding='utf-8') as f:
        json.dump(semantic.to_dict(), f, indent=2)
    print(f"Full semantic graph saved to: {semantic_dict_path}")
    
    print("\n" + "=" * 80)
    print("EXAMPLE COMPLETE")
    print("=" * 80)
    print(f"\nOutput files saved to: {output_dir}")
    print("\nTo visualize the semantic graph:")
    print(f"  dot -Tpng {output_dir}/semantic.dot -o {output_dir}/semantic.png")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

