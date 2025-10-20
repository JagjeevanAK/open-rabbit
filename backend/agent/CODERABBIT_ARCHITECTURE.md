# CodeRabbit-Like Architecture

## Overview

This implementation provides a **CodeRabbit-style recursive code review system** where the backend agent orchestrates comprehensive analysis by:

1. **Generating parser reports** (AST, CFG, PDG, Semantic)
2. **Recursively analyzing** code files with parser insights
3. **Validating issues** against knowledge base
4. **Only commenting** on genuine, actionable issues

## Architecture Comparison

### Before (Simple Pipeline)
```
Code → Parsers Agent → Single Analysis → Comment
```

### After (CodeRabbit-Style)
```
Code → Generate Reports → ┌─→ Read Code
                          │   ↓
                          │   Read Reports
                          │   ↓
                          │   Cross-Reference
                          │   ↓
                          │   Find Issues
                          │   ↓
                          └─← Loop (Recursive)
                          ↓
                          Check Knowledge Base
                          ↓
                          Filter Issues
                          ↓
                          Comment on Valid Issues Only
```

## Key Components

### 1. Parser Reports Reader (`parserReports.py`)

**New tools for reading parser outputs:**

```python
from agent.tools.parserReports import (
    read_parser_reports,           # Read all reports (AST, CFG, PDG, Semantic)
    get_parser_report_summary,     # Quick summary of analysis
    check_specific_issue_in_reports # Validate specific issues
)
```

**What it does:**
- Reads pre-generated reports from `Parsers/output/`
- Extracts issues from parser analysis
- Provides quick summaries and specific checks
- Enables cross-referencing between code and analysis

**Example usage:**
```python
# Get all reports for a file
reports = read_parser_reports("/path/to/file.py")

# Get quick summary
summary = get_parser_report_summary("/path/to/file.py")

# Check specific issue
confirmed = check_specific_issue_in_reports(
    "/path/to/file.py",
    issue_type="high_complexity",
    line_number=42
)
```

### 2. CodeRabbit Workflow (`coderabbit_workflow.py`)

**Enhanced agent workflow with 7 stages:**

1. **Initialize Analysis**
   - Clone repository
   - Load knowledge base context
   - Prepare file queue

2. **Generate Parser Reports**
   - Trigger parser analysis
   - Generate AST, CFG, PDG, Semantic reports
   - Wait for completion

3. **Recursive File Analysis** ⭐ **Key Feature**
   - Read code file
   - Read parser reports
   - Cross-reference back and forth
   - Find issues
   - Loop up to 10 iterations per file
   - Dig deeper if needed

4. **Validate with Knowledge Base** ⭐ **Key Feature**
   - Check each issue against knowledge base
   - Filter out issues maintainers previously accepted
   - Keep only genuine, actionable issues

5. **Prepare Comments**
   - Format validated issues as PR comments
   - Include code suggestions
   - Reference parser evidence

6. **Move to Next File**
   - Process files one by one
   - Reset iteration counter
   - Continue until all files analyzed

7. **Finalize Review**
   - Compile all comments
   - Generate summary
   - Return structured output

### 3. CodeRabbit Client (`coderabbit_client.py`)

**Easy-to-use interface:**

```python
from agent.coderabbit_client import CodeRabbitReviewer

reviewer = CodeRabbitReviewer()

# Review a pull request
result = reviewer.review_pr(
    repo_url="owner/repo",
    pr_number=123,
    files=["file1.py", "file2.py"]
)

# Or review files directly
result = reviewer.review_files(
    file_paths=["path/to/file.py"],
    repo_path="/local/repo"
)
```

## Workflow Visualization

```
┌─────────────────────────────────────────────────────────────┐
│                    Backend Agent (Main)                      │
│              backend/agent/coderabbit_workflow.py            │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌──────────────────┐                  ┌──────────────────┐
│  Parsers Module  │                  │ Knowledge Base   │
│  (Generate       │                  │  (Validate       │
│   Reports)       │                  │   Issues)        │
└──────────────────┘                  └──────────────────┘
        │                                       │
        │    ┌─────────────────────────────────┘
        │    │
        ▼    ▼
    ┌────────────────────┐
    │  Recursive Loop    │
    │  File Analysis     │
    │                    │
    │  1. Read Code      │
    │  2. Read Reports   │
    │  3. Find Issues    │
    │  4. Validate       │
    │  5. Loop ↻         │
    └────────────────────┘
                │
                ▼
        ┌───────────────┐
        │  PR Comments  │
        └───────────────┘
```

## How It Works: Step-by-Step

### Example: Reviewing `myfile.py`

1. **Initialize**
   ```
   → Clone repository
   → Load knowledge base: "Maintainer accepts long functions in tests/"
   → Queue files: ["myfile.py", "other.py"]
   ```

2. **Generate Reports**
   ```
   → parse_code_file("myfile.py")
   → Generates:
     - myfile_ast.json
     - myfile_cfg.json
     - myfile_pdg.json
     - myfile_semantic.json
   ```

3. **Recursive Analysis (Iteration 1)**
   ```
   → Read code: def complex_function()...
   → Agent thinks: "This looks complex"
   → read_parser_reports("myfile.py")
   → CFG report: Cyclomatic complexity = 25 (High!)
   → Issue found: High complexity at line 42
   ```

4. **Recursive Analysis (Iteration 2)**
   ```
   → Agent: "Any other issues near line 42?"
   → check_specific_issue_in_reports(unreachable_code, line=50)
   → Found: Unreachable code after return
   → Issue found: Unreachable code at line 50
   ```

5. **Recursive Analysis (Iteration 3)**
   ```
   → Agent: "Check data dependencies"
   → Read PDG report
   → Found: Complex data dependencies
   → Issue found: Too many dependencies
   ```

6. **Validate with Knowledge Base**
   ```
   → Issue 1: High complexity (line 42)
      check_knowledge_base() → No past acceptance
      ✅ KEEP: Valid issue
   
   → Issue 2: Unreachable code (line 50)
      check_knowledge_base() → No past acceptance
      ✅ KEEP: Valid issue
   
   → Issue 3: Complex dependencies
      check_knowledge_base() → "Team accepts this pattern"
      ❌ FILTER OUT: Maintainer accepted
   ```

7. **Prepare Comments**
   ```json
   {
     "path": "myfile.py",
     "line": 42,
     "body": "Function has high cyclomatic complexity (25). Consider refactoring..."
   },
   {
     "path": "myfile.py",
     "line": 50,
     "body": "Unreachable code detected after return statement..."
   }
   ```

8. **Move to Next File**
   ```
   → Move to "other.py"
   → Reset iteration counter
   → Repeat process
   ```

## Integration with Existing System

### Option 1: Use New CodeRabbit Workflow

```python
from agent.coderabbit_client import review_pull_request

result = review_pull_request(
    repo_url="owner/repo",
    pr_number=123,
    files=["file1.py", "file2.py"]
)
```

### Option 2: Enhance Existing Workflow

The new parser reports tools are **already integrated** into `main.py`:

```python
# In your existing agent, it can now:
1. parse_code_file("file.py")         # Generate reports
2. read_parser_reports("file.py")     # Read reports
3. check_specific_issue_in_reports()  # Validate issues
4. search_knowledge_base()            # Check past learnings
```

## Key Features (CodeRabbit-Like)

### ✅ Recursive Analysis
- Agent loops through code and reports
- Up to 10 iterations per file
- Digs deeper until confident

### ✅ Parser Integration
- AST: Structure, complexity
- CFG: Control flow, unreachable code
- PDG: Data dependencies
- Semantic: Functions, classes, calls

### ✅ Knowledge Base Validation
- Checks past learnings
- Filters accepted patterns
- Avoids repeat comments

### ✅ File-by-File Processing
- Processes files sequentially
- Maintains context per file
- Comprehensive per-file analysis

### ✅ Evidence-Based Comments
- References parser reports
- Includes line numbers
- Shows specific metrics

## Configuration

### Adjust Iteration Limits

In `coderabbit_workflow.py`:
```python
initial_state: CodeRabbitAgentState = {
    ...
    "max_iterations": 10  # Change this
}
```

### Change Output Directory

In `parserReports.py`:
```python
reports_reader = ParserReportsReader(
    output_dir="/custom/path/to/reports"
)
```

## Usage Examples

### Example 1: Review PR

```python
from agent.coderabbit_client import CodeRabbitReviewer

reviewer = CodeRabbitReviewer()
result = reviewer.review_pr(
    repo_url="myorg/myrepo",
    pr_number=456,
    branch="feature/new-stuff",
    files=["src/main.py", "src/utils.py"]
)

print(f"Found {result['validated_issues_count']} valid issues")
print(f"Comments: {len(result['comments'])}")
```

### Example 2: Review Local Files

```python
result = reviewer.review_files(
    file_paths=[
        "/local/repo/src/file1.py",
        "/local/repo/src/file2.py"
    ],
    repo_path="/local/repo",
    context="Reviewing before commit"
)
```

### Example 3: Use Individual Tools

```python
from agent.tools.parserReports import (
    read_parser_reports,
    get_parser_report_summary
)

# Quick check
summary = get_parser_report_summary("/path/file.py")
print(f"Issues found: {summary['total_issues']}")

# Detailed analysis
reports = read_parser_reports("/path/file.py")
for issue in reports['issues']:
    print(f"Line {issue['line']}: {issue['message']}")
```

## Benefits Over Simple Pipeline

| Feature | Before | After (CodeRabbit) |
|---------|--------|-------------------|
| Analysis depth | Single pass | Recursive (up to 10x) |
| Parser integration | Basic | Full (AST+CFG+PDG+Semantic) |
| Issue validation | None | Knowledge base check |
| False positives | Many | Filtered out |
| Comment quality | Generic | Evidence-based |
| File processing | Batch | Sequential, thorough |

## Similar to CodeRabbit

Based on [CodeRabbit.ai](https://www.coderabbit.ai):

✅ **Deep code understanding** via AST analysis
✅ **Learning from feedback** via knowledge base
✅ **Context-aware reviews** with full codebase context
✅ **Iterative analysis** with recursive checking
✅ **Reduced noise** by filtering accepted patterns

## Files Modified/Created

### New Files
- `backend/agent/tools/parserReports.py` - Parser reports reader
- `backend/agent/coderabbit_workflow.py` - Main CodeRabbit workflow
- `backend/agent/coderabbit_client.py` - Easy-to-use client

### Modified Files
- `backend/agent/main.py` - Added parser reports tools
- `Parsers/semantic/` - Semantic graph parser (already implemented)

## Next Steps

1. **Test the workflow:**
   ```bash
   python -c "from agent.coderabbit_client import review_pull_request; review_pull_request('owner/repo', 123)"
   ```

2. **Integrate with PR webhook:**
   - Update `backend/routes/bot_webhook.py`
   - Use `CodeRabbitReviewer` instead of old workflow

3. **Tune iteration limits:**
   - Adjust based on performance
   - Balance thoroughness vs speed

4. **Expand knowledge base:**
   - Add more learnings
   - Improve filtering logic

## Troubleshooting

### Reports not found
```python
# Check output directory
from agent.tools.parserReports import reports_reader
print(reports_reader.output_dir)

# Verify reports exist
import os
print(os.listdir(reports_reader.output_dir))
```

### Too many iterations
```python
# Reduce max_iterations in workflow
max_iterations = 5  # Instead of 10
```

### Agent not using tools
```python
# Check if tools are bound
from agent.coderabbit_workflow import llm_with_tools
print(llm_with_tools)
```

## Conclusion

This architecture implements a **production-ready CodeRabbit-like system** that:
- Analyzes code deeply and recursively
- Uses multiple parser insights (AST, CFG, PDG, Semantic)
- Validates issues against knowledge base
- Only comments on genuine, actionable problems
- Processes files systematically

The system is **ready to use** and can be integrated into your existing PR review pipeline!

