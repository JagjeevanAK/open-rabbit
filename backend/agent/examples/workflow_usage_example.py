"""
Example: Using the Code Review Agent Workflow

This example demonstrates how to use the LangGraph-based code review agent
to analyze pull requests and generate comprehensive reviews.
"""

import asyncio
from agent.workflow import CodeReviewWorkflow, invoke_review
from pprint import pprint
import json


def example_1_review_pr():
    """Example 1: Review a specific pull request"""
    
    print("=" * 80)
    print("EXAMPLE 1: Reviewing a Pull Request")
    print("=" * 80)
    
    result = invoke_review(
        repo_url="facebook/react",
        branch="main",
        pr_description="Add new feature for improved state management",
        changed_files=[
            "src/components/StateManager.tsx",
            "src/hooks/useAdvancedState.ts",
            "src/utils/stateHelpers.ts"
        ]
    )
    
    print("\n📊 Review Results:\n")
    
    if "formatted_review" in result:
        print("✅ Formatted Review Generated:")
        print(json.dumps(result["formatted_review"], indent=2))
    elif "raw_review" in result:
        print("📝 Raw Review:")
        print(result["raw_review"])
    
    print(f"\n🔍 Review Stage: {result['stage']}")
    print(f"📦 Total Messages: {len(result['messages'])}")


def example_2_review_files():
    """Example 2: Review specific files"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Reviewing Specific Files")
    print("=" * 80)
    
    workflow = CodeReviewWorkflow()
    
    result = workflow.review_files(
        file_paths=[
            "src/main.py",
            "src/utils/helpers.py",
            "tests/test_main.py"
        ],
        repo_path="/path/to/local/repo",
        context="Reviewing recent changes to core functionality"
    )
    
    print("\n📊 Review Results:\n")
    pprint(result)


def example_3_custom_workflow():
    """Example 3: Custom workflow with detailed control"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Custom Workflow Execution")
    print("=" * 80)
    
    workflow = CodeReviewWorkflow()
    
    result = workflow.review_pull_request(
        repo_url="https://github.com/microsoft/vscode",
        branch="main",
        pr_description="""
        This PR introduces a new extension API for custom editors.
        
        Changes include:
        - New extension points
        - Updated API documentation
        - Sample implementation
        """,
        changed_files=[
            "src/vs/workbench/api/common/extHost.api.impl.ts",
            "src/vs/workbench/contrib/customEditor/browser/customEditors.ts"
        ]
    )
    
    print("\n📊 Review Results:\n")
    
    print(f"Stage: {result['stage']}")
    print(f"Status: {result['status']}")
    
    if result.get("pr_context"):
        print("\n📦 PR Context:")
        pprint(result["pr_context"])
    
    if result.get("knowledge_context"):
        print("\n🧠 Knowledge Context:")
        pprint(result["knowledge_context"])
    
    if result.get("parser_results"):
        print("\n🔍 Parser Results:")
        pprint(result["parser_results"])
    
    if result.get("formatted_review"):
        print("\n✅ Formatted Review:")
        print(json.dumps(result["formatted_review"], indent=2))


def example_4_simple_review():
    """Example 4: Simplest possible review"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Simple Review")
    print("=" * 80)
    
    result = invoke_review(
        repo_url="torvalds/linux",
        branch="master"
    )
    
    print("\n📊 Review Status:", result["status"])
    print("📦 Messages Count:", len(result["messages"]))


def example_5_streaming_workflow():
    """Example 5: Stream workflow execution (future enhancement)"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Streaming Workflow")
    print("=" * 80)
    print("⚠️  Streaming support coming soon!")
    print("This will allow real-time progress updates during review")


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║                 Code Review Agent - Examples                       ║
    ║                                                                    ║
    ║  LangGraph-powered code review workflow mimicking Code Rabbit      ║
    ╚════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        example_1_review_pr()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nNote: Ensure all dependencies are installed and services are running:")
        print("  - Knowledge Base service (port 8000)")
        print("  - Parsers Celery worker")
        print("  - Redis (for Celery)")
        print("  - OpenAI API key in .env")
