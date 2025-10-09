"""
Example: Unit Test Generation with Code Review Agent

This demonstrates the unit test generation feature integrated into the workflow.
"""

from agent.workflow import invoke_review, CodeReviewWorkflow
import json


def example_1_pr_review_with_tests():
    """Example 1: Review PR and generate unit tests"""
    
    print("=" * 80)
    print("EXAMPLE 1: PR Review with Unit Test Generation")
    print("=" * 80)
    
    result = invoke_review(
        repo_url="facebook/react",
        branch="main",
        pr_description="Add new feature for improved state management",
        changed_files=[
            "src/components/StateManager.tsx",
            "src/hooks/useAdvancedState.ts"
        ],
        generate_tests=True  # Enable unit test generation
    )
    
    print("\n Review Results:\n")
    print(f"Status: {result['status']}")
    print(f"Stage: {result['stage']}")
    
    if "unit_tests" in result and result["unit_tests"]:
        print("\n Unit Tests Generated:")
        print(json.dumps(result["unit_tests"], indent=2))
    
    if "formatted_review" in result:
        print("\n Code Review:")
        print(json.dumps(result["formatted_review"], indent=2))


def example_2_file_review_with_tests():
    """Example 2: Review specific files and generate tests"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 2: File Review with Unit Test Generation")
    print("=" * 80)
    
    workflow = CodeReviewWorkflow()
    
    result = workflow.review_files(
        file_paths=[
            "src/utils/calculator.py",
            "src/services/api_client.py"
        ],
        repo_path="/path/to/repo",
        context="Need comprehensive test coverage for these utility functions",
        generate_tests=True
    )
    
    print("\n Results:\n")
    print(f"Status: {result['status']}")
    
    if "unit_tests" in result:
        print(f"\nUnit tests info: {result['unit_tests']}")


def example_3_api_request_with_tests():
    """Example 3: Using REST API with unit test generation"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 3: REST API Request with Test Generation")
    print("=" * 80)
    
    import requests
    
    payload = {
        "repo_url": "microsoft/vscode",
        "branch": "main",
        "changed_files": [
            "src/vs/workbench/api/common/extHost.api.impl.ts"
        ],
        "pr_description": "Add new extension API",
        "generate_tests": True  # Enable unit test generation
    }
    
    print("\nRequest payload:")
    print(json.dumps(payload, indent=2))
    
    print("\nCURL command:")
    print("""
curl -X POST http://localhost:8080/feedback/review/pr \\
  -H "Content-Type: application/json" \\
  -d '{
    "repo_url": "microsoft/vscode",
    "branch": "main",
    "changed_files": ["src/vs/workbench/api/common/extHost.api.impl.ts"],
    "generate_tests": true
  }'
    """)


def example_4_workflow_stages():
    """Example 4: Understanding the workflow with test generation"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Workflow Stages with Unit Test Generation")
    print("=" * 80)
    
    print("""
    When generate_tests=True, the workflow executes these stages:
    
    1. Context Enrichment
       └─ Clone repo, fetch learnings, read files
    
    2. Static Analysis
       └─ AST/CFG/PDG analysis
    
    3. Code Review
       └─ Generate comprehensive review
    
    4. Unit Test Generation  ← NEW STAGE!
       ├─ Detect testing framework (pytest, jest, vitest, etc.)
       ├─ Read source files
       ├─ Analyze code structure
       ├─ Plan test cases:
       │  ├─ Happy paths
       │  ├─ Edge cases
       │  └─ Error handling
       └─ Generate and write test files
    
    5. Format Output
       └─ Structure as JSON
    
    Tools used in Stage 4:
    • find_test_framework_tool - Detect framework
    • file_reader_tool - Read source code
    • file_writer_tool - Write test files
    • git_add_tool - Stage test files (optional)
    • git_commit_tool - Commit tests (optional)
    """)


def example_5_test_framework_detection():
    """Example 5: How the agent detects testing frameworks"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Test Framework Detection")
    print("=" * 80)
    
    print("""
    The agent automatically detects the testing framework used in your project:
    
    Python Projects:
    ├─ Looks for: test_*.py, *_test.py files
    ├─ Checks config: pytest.ini, pyproject.toml
    └─ Detects: pytest or unittest
    
    JavaScript/TypeScript Projects:
    ├─ Looks for: *.test.ts, *.spec.js files
    ├─ Checks config: jest.config.js, vitest.config.ts, package.json
    └─ Detects: Jest, Vitest, or Mocha
    
    Once detected, the agent:
    1. Follows the exact conventions (imports, assertions, mocking)
    2. Matches the existing test file structure
    3. Uses the same naming patterns
    4. Applies the same testing patterns
    
    Example detected patterns:
    
    pytest:
    ```python
    import pytest
    
    def test_function_name():
        # Arrange
        input_data = 42
        # Act
        result = my_function(input_data)
        # Assert
        assert result == expected
    ```
    
    Jest:
    ```typescript
    import { describe, test, expect } from '@jest/globals';
    
    describe('MyComponent', () => {
        test('should render correctly', () => {
            // Arrange
            const props = { value: 42 };
            // Act
            const result = render(<MyComponent {...props} />);
            // Assert
            expect(result).toMatchSnapshot();
        });
    });
    ```
    """)


def example_6_chain_of_thought():
    """Example 6: Agent's chain of thought during test generation"""
    
    print("\n" + "=" * 80)
    print("EXAMPLE 6: Chain of Thought Process")
    print("=" * 80)
    
    print("""
    When generating tests, the agent thinks step-by-step:
    
    Step 1: Code Analysis
    "This file contains 3 functions: calculate_total, validate_input, format_output"
    "The main purpose is data processing and validation"
    "Key dependencies are: pandas, numpy"
    "Edge cases: empty input, negative numbers, None values"
    
    Step 2: Framework Detection
    "Looking for existing test files..."
    "Found tests/test_data_processor.py using pytest"
    "Confidence: HIGH"
    "Assertion style: assert statements"
    "Mocking approach: pytest.mock"
    
    Step 3: Test Planning
    "I will test these scenarios:"
    1. Happy path: Valid input returns correct output
    2. Edge cases: Empty list, single item, large dataset
    3. Error cases: Invalid types, None input, negative values
    "I need to mock: database connection, API calls"
    "Test file will be named: tests/test_data_processor.py"
    
    Step 4: Test Implementation
    "Starting with setup/fixtures..."
    "Writing happy path tests first..."
    "Adding edge case tests..."
    "Adding error handling tests..."
    
    Step 5: Verification
    "Coverage includes: All public functions"
    "Total test cases: 12"
    "All critical paths tested: YES"
    """)


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║         Unit Test Generation - Usage Examples                      ║
    ║                                                                    ║
    ║  Enable test generation by setting generate_tests=True             ║
    ╚════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Run examples (comment out the API calls for demo)
        example_1_pr_review_with_tests()
        example_2_file_review_with_tests()
        example_3_api_request_with_tests()
        example_4_workflow_stages()
        example_5_test_framework_detection()
        example_6_chain_of_thought()
        
    except Exception as e:
        print(f"\nError: {e}")
        print("\nNote: Make sure the backend server is running:")
        print("  cd backend && python server.py")
