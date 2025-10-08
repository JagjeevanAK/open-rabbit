#!/usr/bin/env python3
"""
Example: Integration of Parser Tools with the Code Review Agent

This demonstrates how the agent can use parser tools during code review.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from agent.tools.Parsers import (
    parse_code_file,
    parse_code_snippet,
    get_parser_capabilities
)


def simulate_agent_review():
    """
    Simulate an agent reviewing code with parser tools.
    
    This shows how the agent would use the tools in a real scenario.
    """
    
    print("\n" + "=" * 70)
    print("SIMULATED AGENT CODE REVIEW WITH PARSER TOOLS")
    print("=" * 70 + "\n")
    
    # Sample code to review
    code_to_review = """
def process_user_data(user_id, data):
    # Fetch user from database
    user = database.get_user(user_id)
    
    if user == None:
        return {"error": "User not found"}
    
    # Process data
    result = []
    for item in data:
        if item['status'] == 'active':
            processed = transform_data(item)
            result.append(processed)
    
    # Update user
    user.data = result
    database.save(user)
    
    return {"success": True, "count": len(result)}

def transform_data(item):
    item['processed'] = True
    item['timestamp'] = get_current_time()
    return item
"""
    
    print("Code Under Review:")
    print("-" * 70)
    print(code_to_review)
    print("-" * 70)
    
    # Step 1: Agent checks parser capabilities
    print("\n[Agent] Checking parser capabilities...")
    capabilities = json.loads(get_parser_capabilities.invoke({}))
    print(f"✓ Parser supports: {', '.join(capabilities['supported_languages'])}")
    
    # Step 2: Agent parses the code
    print("\n[Agent] Analyzing code structure with parser...")
    analysis = json.loads(parse_code_snippet.invoke({
        "code": code_to_review,
        "language": "python"
    }))
    
    if analysis.get("success"):
        results = analysis["results"]
        
        # Step 3: Agent examines AST
        print("\n[Agent] Examining AST...")
        if results.get("ast_report"):
            ast_report = results["ast_report"]
            print(f"  - Found {ast_report.get('statistics', {}).get('total_nodes', 0)} AST nodes")
            print(f"  - Maximum depth: {ast_report.get('statistics', {}).get('max_depth', 0)}")
        
        # Step 4: Agent examines CFG
        print("\n[Agent] Examining Control Flow...")
        if results.get("cfg_report"):
            cfg_report = results["cfg_report"]
            print(f"  - Found {cfg_report.get('total_blocks', 0)} control flow blocks")
            print(f"  - Found {cfg_report.get('total_edges', 0)} edges")
            
            # Check for potential issues
            if cfg_report.get('unreachable_blocks'):
                print("  ⚠️  WARNING: Found unreachable code blocks!")
        
        # Step 5: Agent examines PDG
        print("\n[Agent] Examining Data Dependencies...")
        if results.get("pdg_report"):
            pdg_report = results["pdg_report"]
            print(f"  - Found {pdg_report.get('total_nodes', 0)} PDG nodes")
            print(f"  - Tracking {pdg_report.get('total_variables', 0)} variables")
        
        # Step 6: Agent provides review feedback
        print("\n" + "=" * 70)
        print("AGENT REVIEW FEEDBACK")
        print("=" * 70 + "\n")
        
        print("Based on static analysis, I've identified the following issues:\n")
        
        print("1. 🔴 Code Style Issue:")
        print("   Line: if user == None:")
        print("   Issue: Use 'is None' instead of '== None' for None comparisons")
        print("   Suggestion: if user is None:\n")
        
        print("2. 🟡 Potential Bug:")
        print("   Line: for item in data:")
        print("   Issue: No validation of 'data' parameter before iteration")
        print("   Suggestion: Add check: if not data or not isinstance(data, list):\n")
        
        print("3. 🟢 Missing Error Handling:")
        print("   Function: database.get_user(user_id)")
        print("   Issue: No try-except for database operations")
        print("   Suggestion: Wrap database calls in try-except blocks\n")
        
        print("4. 📊 Complexity Analysis:")
        print(f"   - Functions defined: 2")
        print(f"   - Control flow complexity: Medium")
        print(f"   - Data dependencies: {pdg_report.get('total_variables', 0)} variables tracked")
        print("   - Recommendation: Consider breaking down process_user_data() if it grows\n")
        
    else:
        print(f"✗ Analysis failed: {analysis.get('error')}")
    
    print("=" * 70)
    print("REVIEW COMPLETE")
    print("=" * 70 + "\n")


def example_with_real_file():
    """
    Example showing how to review an actual file from the project.
    """
    
    print("\n" + "=" * 70)
    print("REVIEWING AN ACTUAL PROJECT FILE")
    print("=" * 70 + "\n")
    
    # Try to analyze the Parsers.py file itself
    parsers_file = os.path.join(
        os.path.dirname(__file__),
        "..", "tools", "Parsers.py"
    )
    
    if not os.path.exists(parsers_file):
        print(f"File not found: {parsers_file}")
        return
    
    print(f"[Agent] Analyzing file: {os.path.basename(parsers_file)}\n")
    
    result = json.loads(parse_code_file.invoke({
        "file_path": parsers_file,
        "analysis_type": "full"
    }))
    
    if result.get("success"):
        results = result["results"]
        
        print("✓ Analysis complete!\n")
        
        print("File Statistics:")
        print(f"  Language: {results.get('language', 'N/A')}")
        
        if results.get("ast"):
            print(f"  AST Root: {results['ast']['root_type']}")
            print(f"  Top-level nodes: {results['ast']['num_children']}")
        
        if results.get("cfg"):
            cfg = results["cfg"]
            print(f"  CFG Blocks: {len(cfg.get('blocks', []))}")
        
        if results.get("pdg"):
            pdg = results["pdg"]
            print(f"  PDG Nodes: {len(pdg.get('nodes', []))}")
        
        print("\n[Agent] This file defines the parser integration tools.")
        print("[Agent] Code structure looks good with proper class definitions")
        print("[Agent] and tool decorators for LangChain integration.")
    else:
        print(f"✗ Analysis failed: {result.get('error')}")


def main():
    """Run the integration examples"""
    
    print("\n" + "=" * 70)
    print("PARSER TOOLS INTEGRATION EXAMPLES")
    print("=" * 70)
    
    try:
        simulate_agent_review()
        example_with_real_file()
        
        print("\n" + "=" * 70)
        print("INTEGRATION EXAMPLES COMPLETE")
        print("=" * 70 + "\n")
        
        print("Next Steps:")
        print("1. Start the backend server: cd backend && python server.py")
        print("2. The agent will automatically have access to parser tools")
        print("3. Use tools during code reviews for deep static analysis")
        print("4. Combine with knowledge base tools for comprehensive reviews\n")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
