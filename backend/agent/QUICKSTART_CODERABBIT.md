# CodeRabbit Quick Start Guide

## 🚀 Quick Setup

### 1. Ensure Dependencies

```bash
cd backend
pip install langchain langgraph langchain-openai
```

### 2. Simple Usage

```python
from agent.coderabbit_client import review_pull_request

# Review a PR
result = review_pull_request(
    repo_url="owner/repo",
    pr_number=123,
    files=["src/main.py", "src/utils.py"]
)

print(f"✅ Found {result['validated_issues_count']} issues")
print(f"💬 Generated {result['comments_count']} comments")
```

## 📋 Complete Example

```python
from agent.coderabbit_client import CodeRabbitReviewer

# Initialize
reviewer = CodeRabbitReviewer()

# Review PR
result = reviewer.review_pr(
    repo_url="myorg/myrepo",
    pr_number=456,
    branch="feature/awesome",
    files=[
        "src/app.py",
        "src/models.py",
        "src/utils.py"
    ],
    pr_description="Added new feature X"
)

# Check results
if result['status'] == 'success':
    print(f"📊 Analysis Results:")
    print(f"  - Files analyzed: {len(result['files_analyzed'])}")
    print(f"  - Issues found: {result['total_issues_found']}")
    print(f"  - Valid issues: {result['validated_issues_count']}")
    print(f"  - Comments ready: {result['comments_count']}")
    
    # Show issues
    for issue in result['validated_issues']:
        print(f"\n⚠️  {issue['severity'].upper()}: {issue['message']}")
        print(f"   Line: {issue.get('line', 'N/A')}")
    
    # Show comments
    for comment in result['comments']:
        print(f"\n💬 Comment on {comment['path']}:{comment['line']}")
        print(f"   {comment['body']}")
```

## 🔧 Use Individual Tools

### Read Parser Reports

```python
from agent.tools.parserReports import (
    read_parser_reports,
    get_parser_report_summary,
    check_specific_issue_in_reports
)

# Quick summary
summary = get_parser_report_summary("/path/to/file.py")
print(f"Issues: {summary['total_issues']}")
print(f"High severity: {summary['issues_by_severity']['high']}")

# Full reports
reports = read_parser_reports("/path/to/file.py")
print(f"AST available: {'ast' in reports['available_reports']}")
print(f"Issues found: {len(reports['issues'])}")

# Check specific issue
result = check_specific_issue_in_reports(
    "/path/to/file.py",
    issue_type="high_complexity",
    line_number=42
)
print(f"Issue confirmed: {result['found']}")
```

### Generate Parser Reports First

```python
from agent.tools.Parsers import parse_code_file

# Generate reports (AST, CFG, PDG, Semantic)
result = parse_code_file("/path/to/file.py", include_workflow=True)
print(f"Reports generated: {result['success']}")
print(f"Output dir: {result['output_dir']}")
```

## 🔄 Workflow Stages

The agent goes through these stages:

1. **Initialize** → Clone repo, load knowledge base
2. **Generate Reports** → Trigger parser analysis
3. **Recursive Analysis** → Loop through code + reports (up to 10x)
4. **Validate** → Check knowledge base
5. **Prepare Comments** → Format PR comments
6. **Next File** → Move to next file
7. **Finalize** → Generate summary

## 📁 File Structure

```
backend/agent/
├── tools/
│   ├── parserReports.py      # NEW: Read parser reports
│   ├── Parsers.py             # Generate reports
│   ├── knowledgeBase.py       # Validate issues
│   └── ...
├── coderabbit_workflow.py     # NEW: Main workflow
├── coderabbit_client.py       # NEW: Easy interface
└── main.py                    # Updated: Added new tools
```

## 🎯 What Makes It CodeRabbit-Like?

### Recursive Analysis ✅
```
Read Code → Read Reports → Find Issues → Check More → Loop
```

### Knowledge Base Validation ✅
```
Issue Found → Check KB → Maintainer Accepted? → Filter Out
```

### Parser Integration ✅
```
AST (structure) + CFG (flow) + PDG (dependencies) + Semantic (entities)
```

### Evidence-Based Comments ✅
```
"Function has complexity 25 (from CFG analysis)"
```

## 💡 Tips

### Adjust Iteration Limit
```python
# In coderabbit_workflow.py
"max_iterations": 5  # Default is 10
```

### Custom Output Directory
```python
from agent.tools.parserReports import ParserReportsReader

reader = ParserReportsReader(output_dir="/custom/path")
```

### Debug Mode
```python
# Check what stage the agent is in
print(f"Current stage: {result['stage']}")

# See all messages
for msg in result.get('messages', []):
    print(msg)
```

## 🔍 Checking Results

### View Issues Found
```python
for issue in result['validated_issues']:
    print(f"{issue['severity']}: {issue['message']}")
    print(f"  Source: {issue['source']}")
    print(f"  Line: {issue['line']}")
```

### View Comments
```python
for comment in result['comments']:
    print(f"File: {comment['path']}")
    print(f"Line: {comment['line']}")
    print(f"Comment: {comment['body']}")
```

### Check Parser Reports
```python
file_analysis = result['files_analyzed']
for file_path, analysis in file_analysis.items():
    print(f"File: {file_path}")
    print(f"  Iterations: {analysis.get('iterations', 0)}")
    print(f"  Issues: {len(analysis.get('issues', []))}")
```

## 🚦 Integration with Existing System

### Option 1: Replace Old Workflow

```python
# Before
from agent.workflow import CodeReviewWorkflow
workflow = CodeReviewWorkflow()

# After
from agent.coderabbit_client import CodeRabbitReviewer
reviewer = CodeRabbitReviewer()
```

### Option 2: Use Both

```python
# Use old workflow for quick reviews
from agent.workflow import invoke_review
quick_result = invoke_review(repo_url, pr_number)

# Use CodeRabbit workflow for thorough reviews
from agent.coderabbit_client import review_pull_request
thorough_result = review_pull_request(repo_url, pr_number)
```

### Option 3: Enhance Existing Agent

The new tools are **already added** to `main.py`:
```python
# Your existing agent can now use:
- read_parser_reports()
- get_parser_report_summary()
- check_specific_issue_in_reports()
```

## 📊 Example Output

```json
{
  "status": "success",
  "stage": "complete",
  "total_issues_found": 15,
  "validated_issues_count": 8,
  "comments_count": 8,
  "validated_issues": [
    {
      "type": "high_complexity",
      "severity": "medium",
      "line": 42,
      "function": "process_data",
      "complexity": 25,
      "message": "Function 'process_data' has high cyclomatic complexity (25)"
    },
    {
      "type": "unreachable_code",
      "severity": "high",
      "line": 50,
      "message": "Unreachable code detected at line 50"
    }
  ],
  "comments": [
    {
      "path": "src/main.py",
      "line": 42,
      "body": "Function has high cyclomatic complexity (25)..."
    }
  ]
}
```

## 🎓 Learn More

- Full documentation: `CODERABBIT_ARCHITECTURE.md`
- Parser reports: `tools/parserReports.py`
- Main workflow: `coderabbit_workflow.py`
- Client interface: `coderabbit_client.py`

## 🐛 Troubleshooting

### "Reports not found"
```python
# 1. Generate reports first
from agent.tools.Parsers import parse_code_file
parse_code_file("/path/file.py")

# 2. Check output directory
from agent.tools.parserReports import reports_reader
print(reports_reader.output_dir)
```

### "Too slow"
```python
# Reduce iterations
"max_iterations": 3  # Instead of 10
```

### "Not finding issues"
```python
# Check parser reports directly
reports = read_parser_reports("/path/file.py")
print(f"Issues in reports: {len(reports['issues'])}")
```

## ✨ You're Ready!

```python
from agent.coderabbit_client import review_pull_request

# Start reviewing!
review_pull_request("your/repo", 123)
```

🎉 Your CodeRabbit-like system is ready to use!

