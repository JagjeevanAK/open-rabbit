#!/usr/bin/env python3
"""
Quick Test Script for CFG and PDG Pipeline
Run this to test the pipeline with a simple example
"""

from pipeline import AnalysisPipeline


def main():
    print("\n" + "=" * 70)
    print("🚀 CFG & PDG Pipeline - Quick Test")
    print("=" * 70)
    
    # Test code
    code = """
def calculate(x, y):
    if x > y:
        result = x + y
    else:
        result = x * y
    return result

a = 10
b = 5
total = calculate(a, b)
print(total)
"""
    
    print("\nTest Code:")
    print(code)
    print("-" * 70)
    
    # Create pipeline
    pipeline = AnalysisPipeline("python")
    
    # Run analysis
    print("\n📊 Running Analysis Pipeline...")
    results = pipeline.run_full_pipeline(code)
    
    # Print summary
    pipeline.print_summary()
    
    # Show CFG details
    print("\n📈 CFG Details:")
    cfg = results['cfg']
    print(f"  Total blocks: {len(cfg['blocks'])}")
    print(f"  Entry block: {cfg['entry_block']}")
    print(f"  Exit block: {cfg['exit_block']}")
    
    print("\n  Block connections:")
    for block_id, block in cfg['blocks'].items():
        if block['successors']:
            print(f"    Block {block_id} → {block['successors']}")
    
    # Show PDG details
    print("\n📉 PDG Details:")
    pdg = results['pdg']
    print(f"  Total nodes: {len(pdg['nodes'])}")
    print(f"  Variables: {len(pdg['variables'])}")
    
    print("\n  Variables and their definitions:")
    for var_name, var_info in pdg['variables'].items():
        print(f"    {var_name}: defined at nodes {var_info['definitions']}")
    
    print("\n  Data dependencies:")
    for node_id, node in pdg['nodes'].items():
        if node['data_dependencies']:
            print(f"    Node {node_id} depends on: {node['data_dependencies']}")
    
    # Export results
    print("\n💾 Exporting Results...")
    pipeline.export_to_json("./output/test_results.json")
    pipeline.export_visualizations("./output/test")
    
    print("\n✅ Test Complete!")
    print("\nGenerated files:")
    print("  - output/test_results.json")
    print("  - output/test/cfg.dot")
    print("  - output/test/pdg.dot")
    
    print("\n💡 To visualize the graphs:")
    print("  dot -Tpng output/test/cfg.dot -o output/test/cfg.png")
    print("  dot -Tpng output/test/pdg.dot -o output/test/pdg.png")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
