"""
Example usage of Knowledge Base tools for code review enrichment.

This file demonstrates how to use the knowledge base retrieval tools
to enrich prompts with historical learnings and project-specific context.
"""

from agent.tools.knowledgeBase import (
    search_knowledge_base,
    get_pr_learnings,
    format_review_context,
    KnowledgeBaseClient,
)
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


# ============================================================================
# Example 1: Simple Knowledge Base Search
# ============================================================================

def example_search_learnings():
    """Search for general topic learnings."""
    print("=" * 80)
    print("Example 1: Searching for 'error handling' learnings")
    print("=" * 80)
    
    # Use the LangChain tool directly
    result = search_knowledge_base.invoke({
        "query": "error handling best practices",
        "k": 3,
        "language_filter": "python"
    })
    
    print(result)
    print("\n")


# ============================================================================
# Example 2: Get PR-Specific Learnings
# ============================================================================

def example_pr_learnings():
    """Get learnings specific to a PR context."""
    print("=" * 80)
    print("Example 2: Getting PR-specific learnings")
    print("=" * 80)
    
    result = get_pr_learnings.invoke({
        "pr_description": "Add authentication middleware for API endpoints",
        "changed_files": [
            "backend/middleware/auth.py",
            "backend/routes/user.py",
            "tests/test_auth.py"
        ],
        "repo_name": "JagjeevanAK/open-rabbit",
        "k": 5
    })
    
    print(result)
    print("\n")


# ============================================================================
# Example 3: Generate Comprehensive Review Context
# ============================================================================

def example_comprehensive_context():
    """Generate a full review context with multiple knowledge sources."""
    print("=" * 80)
    print("Example 3: Comprehensive review context")
    print("=" * 80)
    
    result = format_review_context.invoke({
        "pr_description": "Refactor database connection handling",
        "changed_files": [
            "backend/db/database.py",
            "backend/db/models.py",
            "backend/main.py"
        ],
        "repo_name": "JagjeevanAK/open-rabbit",
        "additional_queries": [
            "database connection pooling",
            "SQLAlchemy best practices",
            "error handling in database operations"
        ]
    })
    
    print(result)
    print("\n")


# ============================================================================
# Example 4: Using Knowledge Base with LangChain Agent
# ============================================================================

def example_with_agent():
    """Use knowledge base tools with a LangChain agent for code review."""
    print("=" * 80)
    print("Example 4: Using knowledge base in agent workflow")
    print("=" * 80)
    
    # Create an agent with tools
    llm = ChatOpenAI(model="gpt-4o")
    tools = [search_knowledge_base, get_pr_learnings, format_review_context]
    llm_with_tools = llm.bind_tools(tools)
    
    # System message with instructions
    system_msg = SystemMessage(content="""
    You are a code review agent. Use the knowledge base tools to gather 
    relevant project learnings before providing review feedback.
    
    Always start by:
    1. Using get_pr_learnings to understand PR-specific context
    2. Using search_knowledge_base for any specific topics you want to investigate
    3. Applying the learnings to provide informed, consistent feedback
    """)
    
    # Example review request
    human_msg = HumanMessage(content="""
    Please review this pull request:
    
    **PR Title**: Add rate limiting to API endpoints
    
    **Description**: 
    This PR adds rate limiting middleware to prevent API abuse. It uses Redis 
    as a backend for tracking request counts per user.
    
    **Changed Files**:
    - backend/middleware/ratelimit.py (new file)
    - backend/main.py (modified)
    - backend/requirements.txt (modified)
    
    **Key Changes**:
    - Implemented sliding window rate limiter
    - Added Redis connection configuration
    - Applied rate limiting to user routes
    
    Please check the knowledge base for relevant learnings about rate limiting,
    Redis usage, and middleware patterns in this project.
    """)
    
    # Get agent response
    response = llm_with_tools.invoke([system_msg, human_msg])
    
    print("Agent Response:")
    print(response.content)
    
    # If the agent wants to use tools, execute them
    if response.tool_calls:
        print("\n" + "=" * 80)
        print("Agent requested tool calls:")
        for tool_call in response.tool_calls:
            print(f"\n- Tool: {tool_call['name']}")
            print(f"  Args: {tool_call['args']}")


# ============================================================================
# Example 5: Manual Client Usage (without LangChain)
# ============================================================================

def example_direct_client():
    """Use the KnowledgeBaseClient directly without LangChain."""
    print("=" * 80)
    print("Example 5: Direct client usage")
    print("=" * 80)
    
    client = KnowledgeBaseClient()
    
    # Search for learnings
    result = client.search_learnings(
        query="dependency management and version updates",
        k=3,
        repo_filter="JagjeevanAK/open-rabbit",
        language_filter="python",
        min_confidence=0.5
    )
    
    print(f"Found {result.get('total_results', 0)} learnings")
    print(f"Search took {result.get('search_time_ms', 0):.2f}ms\n")
    
    for idx, learning in enumerate(result.get('results', []), 1):
        print(f"{idx}. {learning.get('learning_text', '')}")
        print(f"   Language: {learning.get('language', 'N/A')}")
        print(f"   Confidence: {learning.get('confidence_score', 0):.2f}")
        print()


# ============================================================================
# Example 6: Enriching a Code Review Prompt
# ============================================================================

def example_enrich_prompt():
    """Show how to enrich a code review prompt with knowledge base context."""
    print("=" * 80)
    print("Example 6: Enriching a review prompt")
    print("=" * 80)
    
    # 1. Get PR context
    pr_context = get_pr_learnings.invoke({
        "pr_description": "Add GraphQL API endpoint",
        "changed_files": ["backend/graphql/schema.py", "backend/graphql/resolvers.py"],
        "repo_name": "JagjeevanAK/open-rabbit",
        "k": 3
    })
    
    # 2. Search for specific topics
    api_patterns = search_knowledge_base.invoke({
        "query": "API design and validation patterns",
        "k": 3,
        "language_filter": "python"
    })
    
    # 3. Build enriched prompt
    enriched_prompt = f"""
# Code Review Request

## Pull Request Information
- **Title**: Add GraphQL API endpoint
- **Files**: backend/graphql/schema.py, backend/graphql/resolvers.py
- **Description**: Implements GraphQL endpoint for querying user data

## Historical Context (from Knowledge Base)

### PR-Specific Learnings
{pr_context}

### Relevant API Patterns
{api_patterns}

## Code to Review
```python
# backend/graphql/schema.py
import graphene

class UserType(graphene.ObjectType):
    id = graphene.ID()
    name = graphene.String()
    email = graphene.String()

class Query(graphene.ObjectType):
    user = graphene.Field(UserType, id=graphene.ID(required=True))
    
    def resolve_user(self, info, id):
        # TODO: Add validation and error handling
        return get_user_by_id(id)
```

## Review Instructions
Please review this code considering:
1. The historical learnings from similar PRs
2. Project-specific API patterns
3. Best practices for GraphQL implementations
4. Any security or validation concerns
"""
    
    print(enriched_prompt)


# ============================================================================
# Main execution
# ============================================================================

if __name__ == "__main__":
    import sys
    
    examples = {
        "1": ("Simple search", example_search_learnings),
        "2": ("PR learnings", example_pr_learnings),
        "3": ("Comprehensive context", example_comprehensive_context),
        "4": ("With agent", example_with_agent),
        "5": ("Direct client", example_direct_client),
        "6": ("Enrich prompt", example_enrich_prompt),
    }
    
    print("Knowledge Base Tools - Examples\n")
    print("Available examples:")
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    print(f"  all. Run all examples")
    print()
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("Select example (1-6 or 'all'): ").strip()
    
    if choice == "all":
        for name, func in examples.values():
            try:
                func()
            except Exception as e:
                print(f"Error in {name}: {e}\n")
    elif choice in examples:
        name, func = examples[choice]
        try:
            func()
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Invalid choice!")
