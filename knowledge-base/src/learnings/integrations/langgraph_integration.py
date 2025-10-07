"""
LangGraph integration for injecting learnings into code review workflows.

This module provides nodes and utilities for integrating the Learnings
system into LangGraph-based code review pipelines.
"""

from typing import TypedDict, List, Annotated
from operator import add
from langgraph.graph import StateGraph, END
from src.learnings.core.retriever import LearningRetriever
from src.learnings.core.storage import LearningStorage
from src.learnings.core.config import get_settings


# ============================================================================
# State Definitions
# ============================================================================

class ReviewState(TypedDict):
    """
    State schema for code review workflow.
    
    This matches a typical LangGraph state for PR reviews.
    """
    # PR Context
    repo_name: str
    pr_number: int
    pr_title: str
    pr_description: str
    changed_files: List[str]
    
    # Review Process
    code_snippets: List[dict]
    review_comments: Annotated[List[str], add]
    
    # Learnings Context
    learnings_context: str
    learnings_retrieved: List[dict]


# ============================================================================
# LangGraph Nodes
# ============================================================================

class LearningsNode:
    """
    LangGraph node for retrieving and injecting learnings.
    
    This node can be inserted into any review workflow to augment
    the LLM context with relevant past learnings.
    """
    
    def __init__(self):
        settings = get_settings()
        storage = LearningStorage(settings)
        self.retriever = LearningRetriever(storage, settings)
    
    def __call__(self, state: ReviewState) -> ReviewState:
        """
        Retrieve learnings and inject into state.
        
        This is the main node function that LangGraph will call.
        """
        print(f"[LearningsNode] Retrieving learnings for PR #{state['pr_number']}")
        
        # Retrieve learnings relevant to this PR
        learnings = self.retriever.get_learnings_for_pr_context(
            pr_description=f"{state['pr_title']} - {state['pr_description']}",
            changed_files=state['changed_files'],
            repo_name=state['repo_name'],
            k=5
        )
        
        # Format for context injection
        context = self.retriever.format_for_context(learnings, max_learnings=5)
        
        # Update state
        state['learnings_context'] = context
        state['learnings_retrieved'] = [
            {
                "learning_id": l.learning_id,
                "learning_text": l.learning_text,
                "confidence": l.confidence_score
            }
            for l in learnings
        ]
        
        print(f"[LearningsNode] Retrieved {len(learnings)} learnings")
        
        return state


# ============================================================================
# Helper Functions for LangGraph Integration
# ============================================================================

def create_review_prompt_with_learnings(
    base_prompt: str,
    learnings_context: str,
    code_snippet: str
) -> str:
    """
    Construct a review prompt that includes learnings context.
    
    This is a utility function for building LLM prompts in review nodes.
    """
    return f"""
{base_prompt}

{learnings_context}

## Code to Review:
```
{code_snippet}
```

Provide your review considering the project learnings above.
"""


def should_inject_learnings(state: ReviewState) -> bool:
    """
    Conditional edge logic: decide if learnings injection is needed.
    
    Use this in LangGraph conditional edges to skip retrieval
    for trivial PRs or when no files changed.
    """
    # Skip if no files changed
    if not state.get('changed_files'):
        return False
    
    # Skip for documentation-only PRs
    doc_extensions = {'.md', '.rst', '.txt'}
    all_docs = all(
        any(f.endswith(ext) for ext in doc_extensions)
        for f in state['changed_files']
    )
    if all_docs:
        return False
    
    return True


# ============================================================================
# Example LangGraph Workflow
# ============================================================================

def create_review_workflow():
    """
    Example: Create a complete review workflow with learnings integration.
    
    This demonstrates how to build a LangGraph workflow that includes
    learnings retrieval as a node in the review pipeline.
    """
    
    # Initialize workflow
    workflow = StateGraph(ReviewState)
    
    # Initialize nodes
    learnings_node = LearningsNode()
    
    # Add nodes
    workflow.add_node("fetch_pr_data", fetch_pr_data_node)
    workflow.add_node("inject_learnings", learnings_node)
    workflow.add_node("analyze_code", analyze_code_node)
    workflow.add_node("generate_review", generate_review_node)
    
    # Define edges
    workflow.set_entry_point("fetch_pr_data")
    
    # Conditional edge: only inject learnings if needed
    workflow.add_conditional_edges(
        "fetch_pr_data",
        should_inject_learnings,
        {
            True: "inject_learnings",
            False: "analyze_code"
        }
    )
    
    workflow.add_edge("inject_learnings", "analyze_code")
    workflow.add_edge("analyze_code", "generate_review")
    workflow.add_edge("generate_review", END)
    
    return workflow.compile()


# ============================================================================
# Placeholder Nodes (for complete example)
# ============================================================================

def fetch_pr_data_node(state: ReviewState) -> ReviewState:
    """Placeholder: fetch PR data from GitHub/GitLab API."""
    print("[fetch_pr_data_node] Fetching PR data...")
    # In production, call GitHub API here
    return state


def analyze_code_node(state: ReviewState) -> ReviewState:
    """Placeholder: analyze code for issues."""
    print("[analyze_code_node] Analyzing code...")
    # In production, run static analysis here
    return state


def generate_review_node(state: ReviewState) -> ReviewState:
    """
    Generate review comments using LLM with learnings context.
    
    This is where the learnings context gets injected into the prompt.
    """
    print("[generate_review_node] Generating review with learnings context...")
    
    # Example: use learnings in prompt
    base_prompt = "You are an expert code reviewer. Review this code for quality, bugs, and best practices."
    
    learnings_context = state.get('learnings_context', '')
    
    for snippet in state.get('code_snippets', []):
        prompt = create_review_prompt_with_learnings(
            base_prompt=base_prompt,
            learnings_context=learnings_context,
            code_snippet=snippet['code']
        )
        
        # Call LLM here (placeholder)
        # review = llm.invoke(prompt)
        # state['review_comments'].append(review)
        
        print(f"  Generated review for {snippet['file']}")
    
    return state


# ============================================================================
# Standalone Usage Example
# ============================================================================

if __name__ == "__main__":
    """
    Example: Run learnings retrieval standalone.
    """
    print("=== Learnings LangGraph Integration Example ===\n")
    
    # Create a sample state
    sample_state: ReviewState = {
        "repo_name": "acme/web-app",
        "pr_number": 1234,
        "pr_title": "Add user authentication",
        "pr_description": "Implements JWT-based authentication for API endpoints",
        "changed_files": ["src/auth.py", "src/middleware.py", "tests/test_auth.py"],
        "code_snippets": [],
        "review_comments": [],
        "learnings_context": "",
        "learnings_retrieved": []
    }
    
    # Initialize node
    learnings_node = LearningsNode()
    
    # Run node
    updated_state = learnings_node(sample_state)
    
    # Display results
    print("\n=== Retrieved Learnings ===")
    print(updated_state['learnings_context'])
    
    print("\n=== Learnings Metadata ===")
    for learning in updated_state['learnings_retrieved']:
        print(f"  - {learning['learning_id'][:8]}... (confidence: {learning['confidence']:.2f})")
        print(f"    {learning['learning_text'][:80]}...")
