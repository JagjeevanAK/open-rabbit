"""
Workflow Visualization and State Inspector

This module helps visualize the LangGraph workflow and inspect state transitions.
"""

from typing import Dict, Any
from agent.main import app
import json


def print_workflow_graph():
    """Print the workflow graph structure"""
    
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║              Code Review Agent - Workflow Graph                    ║
    ╚════════════════════════════════════════════════════════════════════╝
    
    Flow Architecture (mimicking Code Rabbit):
    
    ┌─────────────────────────────────────────────────────────────────┐
    │                         ENTRY POINT                             │
    └─────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │  STAGE 1: Context Enrichment                                    │
    │  ├─ Clone Repository (git_clone_tool)                           │
    │  ├─ Fetch Knowledge Base Learnings (get_pr_learnings)           │
    │  ├─ Search Historical Patterns (search_knowledge_base)          │
    │  └─ Read Changed Files (file_reader_tool)                       │
    └─────────────────────────┬───────────────────────────────────────┘
                              │
                              ├─────► [Tools] ◄────┐
                              │                     │
                              ▼                     │
    ┌─────────────────────────────────────────────────────────────────┐
    │  STAGE 2: Static Analysis                                       │
    │  ├─ Trigger Parsers Agent (analyze_changed_files)               │
    │  ├─ AST Analysis (parse_code_file)                              │
    │  ├─ CFG Generation                                              │
    │  └─ PDG Analysis                                                │
    └─────────────────────────┬───────────────────────────────────────┘
                              │                     │
                              ├─────► [Tools] ◄────┤
                              │                     │
                              ▼                     │
    ┌─────────────────────────────────────────────────────────────────┐
    │  STAGE 3: Code Review                                           │
    │  ├─ Synthesize All Context                                      │
    │  ├─ Apply Knowledge Base Learnings                              │
    │  ├─ Review Static Analysis Results                              │
    │  └─ Generate Actionable Feedback                                │
    └─────────────────────────┬───────────────────────────────────────┘
                              │                     │
                              ├─────► [Tools] ◄────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │  STAGE 4: Format Output                                         │
    │  ├─ Structure Review as JSON                                    │
    │  ├─ Format Comments (inline/diff/range)                         │
    │  └─ Generate Summary                                            │
    └─────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                            END                                  │
    └─────────────────────────────────────────────────────────────────┘
    
    Tools Available:
    ├─ Knowledge Base Tools:
    │  ├─ search_knowledge_base
    │  ├─ get_pr_learnings
    │  └─ format_review_context
    │
    ├─ Parser Tools:
    │  ├─ parse_code_file
    │  ├─ analyze_changed_files
    │  └─ get_parser_capabilities
    │
    ├─ Git Tools:
    │  ├─ git_clone_tool
    │  ├─ get_repo_structure
    │  ├─ git_get_pr_files
    │  ├─ git_get_pr_diff
    │  └─ git_get_file_content
    │
    └─ File Tools:
       ├─ file_reader_tool
       ├─ list_files_tool
       └─ search_in_file_tool
    """)


def print_state_schema():
    """Print the state schema"""
    
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║                    Agent State Schema                              ║
    ╚════════════════════════════════════════════════════════════════════╝
    
    AgentState {
        messages: List[BaseMessage]
            - Conversation history
            - Tool calls and responses
            - System prompts
        
        pr_context: Dict
            - Repository information
            - Changed files
            - PR metadata
        
        knowledge_context: Dict
            - Historical learnings
            - Accepted/rejected patterns
            - Project-specific guidelines
        
        parser_results: Dict
            - AST analysis
            - CFG outputs
            - PDG insights
            - AI-generated recommendations
        
        review_output: Dict
            - Formatted review comments
            - Summary
            - Metadata
        
        current_stage: str
            - "context_enrichment"
            - "static_analysis"
            - "code_review"
            - "complete"
    }
    """)


def print_routing_logic():
    """Print the routing logic"""
    
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║                      Routing Logic                                 ║
    ╚════════════════════════════════════════════════════════════════════╝
    
    Conditional Routing:
    
    1. After Context Enrichment:
       IF last_message.tool_calls → TOOLS node
       ELSE → Static Analysis node
    
    2. After Static Analysis:
       IF last_message.tool_calls → TOOLS node
       ELSE → Code Review node
    
    3. After Code Review:
       IF last_message.tool_calls → TOOLS node
       ELSE → Format Output node
    
    4. After Tools:
       Based on current_stage:
       - "context_enrichment" → Context Enrichment node
       - "static_analysis" → Static Analysis node
       - "code_review" → Code Review node
       - default → Context Enrichment node
    
    5. After Format Output:
       → END (workflow complete)
    """)


def print_tool_descriptions():
    """Print detailed tool descriptions"""
    
    tools_info = {
        "Knowledge Base Tools": {
            "search_knowledge_base": "Search historical learnings by topic/pattern",
            "get_pr_learnings": "Get contextual learnings for current PR",
            "format_review_context": "Format knowledge base context for review"
        },
        "Parser Tools": {
            "parse_code_file": "Trigger full AST/CFG/PDG analysis for a file",
            "analyze_changed_files": "Batch analyze multiple files",
            "get_parser_capabilities": "Check supported languages and features"
        },
        "Git Tools": {
            "git_clone_tool": "Clone repository for analysis",
            "get_repo_structure": "Get repository file structure",
            "git_get_pr_files": "Get list of files in a PR",
            "git_get_pr_diff": "Get diff for PR changes",
            "git_get_file_content": "Read specific file content"
        },
        "File Tools": {
            "file_reader_tool": "Read file contents",
            "list_files_tool": "List files in directory",
            "search_in_file_tool": "Search within file contents"
        }
    }
    
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║                      Available Tools                               ║
    ╚════════════════════════════════════════════════════════════════════╝
    """)
    
    for category, tools in tools_info.items():
        print(f"\n{category}:")
        for tool_name, description in tools.items():
            print(f"  • {tool_name}")
            print(f"    └─ {description}")


def visualize_workflow():
    """Main function to visualize entire workflow"""
    
    print_workflow_graph()
    print("\n" + "=" * 80 + "\n")
    
    print_state_schema()
    print("\n" + "=" * 80 + "\n")
    
    print_routing_logic()
    print("\n" + "=" * 80 + "\n")
    
    print_tool_descriptions()
    
    print("""
    
    ╔════════════════════════════════════════════════════════════════════╗
    ║                    Workflow Characteristics                        ║
    ╚════════════════════════════════════════════════════════════════════╝
    
    ✓ Multi-stage pipeline with clear separation of concerns
    ✓ Tool-augmented LLM at each stage
    ✓ Conditional routing based on tool calls
    ✓ State preservation across stages
    ✓ Context accumulation (knowledge + analysis + review)
    ✓ Structured output formatting
    
    Architecture Benefits:
    ├─ Modularity: Each stage is independent and testable
    ├─ Extensibility: Easy to add new tools or stages
    ├─ Observability: Clear state transitions and routing
    └─ Reliability: Structured error handling at each stage
    """)


if __name__ == "__main__":
    visualize_workflow()
