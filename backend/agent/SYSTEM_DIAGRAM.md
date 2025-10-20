# CodeRabbit System Architecture Diagram

## Complete System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GitHub Pull Request                              │
│                         (New PR / Updated PR)                            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Webhook Handler                                     │
│                   backend/routes/bot_webhook.py                          │
│                                                                           │
│  • Receives PR event                                                     │
│  • Extracts: repo, branch, files, PR number                             │
│  • Triggers CodeRabbit review                                            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   CodeRabbit Client Interface                            │
│                  backend/agent/coderabbit_client.py                      │
│                                                                           │
│  CodeRabbitReviewer().review_pr(repo_url, pr_number, files)            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    CodeRabbit Workflow Engine                            │
│                backend/agent/coderabbit_workflow.py                      │
│                                                                           │
│  7-Stage Workflow:                                                       │
│                                                                           │
│  Stage 1: Initialize Analysis                                            │
│  ├─→ Clone repository                                                    │
│  ├─→ Load knowledge base context                                         │
│  └─→ Prepare file queue                                                  │
│                                                                           │
│  Stage 2: Generate Parser Reports                                        │
│  ├─→ For current file                                                    │
│  ├─→ Trigger parse_code_file()                                          │
│  └─→ Wait for AST, CFG, PDG, Semantic reports                           │
│                                                                           │
│  Stage 3: Recursive File Analysis ⭐ CORE LOOP                          │
│  ┌────────────────────────────────────────┐                             │
│  │  Iteration 1:                          │                             │
│  │  ├─→ Read code (file_reader_tool)     │                             │
│  │  ├─→ Read reports (read_parser_reports)│                             │
│  │  ├─→ Find issue: "complexity=25"      │                             │
│  │  └─→ Continue analyzing               │                             │
│  │                                        │                             │
│  │  Iteration 2:                          │                             │
│  │  ├─→ Dig deeper around line 42        │                             │
│  │  ├─→ Check unreachable code           │                             │
│  │  ├─→ Find more issues                 │                             │
│  │  └─→ Continue if needed               │                             │
│  │                                        │                             │
│  │  ...up to 10 iterations                │                             │
│  └────────────────────────────────────────┘                             │
│                                                                           │
│  Stage 4: Validate with Knowledge Base ⭐                               │
│  ├─→ For each issue found                                                │
│  ├─→ Check: search_knowledge_base()                                      │
│  ├─→ Check: get_pr_learnings()                                          │
│  ├─→ Filter: Maintainer accepted? → Skip                                │
│  └─→ Keep: Valid issues only                                             │
│                                                                           │
│  Stage 5: Prepare Comments                                               │
│  ├─→ Format as PR comments                                               │
│  ├─→ Include code suggestions                                            │
│  └─→ Reference parser evidence                                           │
│                                                                           │
│  Stage 6: Move to Next File                                              │
│  ├─→ Pop next file from queue                                            │
│  ├─→ Reset iteration counter                                             │
│  └─→ Go to Stage 2 (or Stage 7 if done)                                │
│                                                                           │
│  Stage 7: Finalize Review                                                │
│  ├─→ Compile all comments                                                │
│  ├─→ Generate summary                                                    │
│  └─→ Return structured output                                            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     │                               │
                     ▼                               ▼
    ┌────────────────────────────┐   ┌────────────────────────────┐
    │     Tools: Parsers         │   │  Tools: Knowledge Base     │
    │  tools/Parsers.py          │   │  tools/knowledgeBase.py    │
    │  tools/parserReports.py    │   │                            │
    │                            │   │  • search_knowledge_base() │
    │  • parse_code_file()       │   │  • get_pr_learnings()      │
    │  • analyze_changed_files() │   │  • format_review_context() │
    │  • read_parser_reports()   │   │                            │
    │  • get_parser_report_summary()│  │                            │
    │  • check_specific_issue()  │   │                            │
    └────────────┬───────────────┘   └────────────┬───────────────┘
                 │                                 │
                 ▼                                 ▼
    ┌────────────────────────────┐   ┌────────────────────────────┐
    │   Parsers Module           │   │  Knowledge Base            │
    │   Parsers/                 │   │  knowledge-base/           │
    │                            │   │                            │
    │  Pipeline:                 │   │  Learnings:                │
    │  └─→ AST Parser            │   │  └─→ Past PR patterns      │
    │  └─→ CFG Builder           │   │  └─→ Maintainer preferences│
    │  └─→ PDG Builder           │   │  └─→ Accepted issues       │
    │  └─→ Semantic Builder      │   │                            │
    │                            │   │                            │
    │  Output: Parsers/output/   │   │                            │
    │  └─→ file_ast.json         │   │                            │
    │  └─→ file_cfg.json         │   │                            │
    │  └─→ file_pdg.json         │   │                            │
    │  └─→ file_semantic.json    │   │                            │
    └────────────────────────────┘   └────────────────────────────┘
```

## Data Flow Sequence

```
1. PR Event
   ↓
2. Extract Files: ["main.py", "utils.py", "models.py"]
   ↓
3. Initialize: Clone repo, Load KB
   ↓
4. START: Process main.py
   ↓
5. Generate Reports:
   - parse_code_file("main.py")
   - Wait for: main_ast.json, main_cfg.json, main_pdg.json, main_semantic.json
   ↓
6. Recursive Analysis (Iteration 1):
   - file_reader_tool("main.py")
   - read_parser_reports("main.py")
   - Agent thinks: "I see a complex function at line 42"
   - check_specific_issue_in_reports("main.py", "high_complexity", 42)
   - Confirmed: Complexity = 25 (from CFG)
   - Issue #1 found
   ↓
7. Recursive Analysis (Iteration 2):
   - Agent: "Let me check around line 42 more"
   - Finds unreachable code at line 50
   - Finds missing docs at line 45
   - Issues #2, #3 found
   ↓
8. Recursive Analysis (Iteration 3):
   - Agent: "Check data dependencies"
   - read_parser_reports("main.py") → PDG section
   - Finds complex dependencies
   - Issue #4 found
   ↓
9. Validate with KB:
   - Issue #1: search_knowledge_base("high complexity") → No past acceptance → ✅ Keep
   - Issue #2: search_knowledge_base("unreachable code") → No past acceptance → ✅ Keep
   - Issue #3: search_knowledge_base("missing docs") → Team doesn't require → ❌ Filter
   - Issue #4: get_pr_learnings() → "Complex deps accepted in utils" → ❌ Filter
   ↓
10. Prepare Comments:
    - Format Issues #1, #2 as PR comments
    - Add code suggestions
    - Reference parser evidence
   ↓
11. NEXT: Process utils.py
    - Reset iterations
    - Repeat steps 5-10
   ↓
12. NEXT: Process models.py
    - Reset iterations
    - Repeat steps 5-10
   ↓
13. Finalize:
    - Compile all comments from all files
    - Generate summary
    - Return: { comments: [...], summary: "..." }
   ↓
14. Post to GitHub:
    - For each comment: POST /repos/:owner/:repo/pulls/:number/comments
```

## Component Interactions

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Tools Available                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Parser Tools (NEW):                                            │
│  ├─ read_parser_reports(file)          Read all reports         │
│  ├─ get_parser_report_summary(file)    Quick overview          │
│  └─ check_specific_issue_in_reports()  Validate issues         │
│                                                                  │
│  Parser Generation:                                             │
│  ├─ parse_code_file(file)              Trigger analysis        │
│  └─ analyze_changed_files(files)       Batch analysis          │
│                                                                  │
│  Knowledge Base:                                                │
│  ├─ search_knowledge_base(query)       Search learnings        │
│  ├─ get_pr_learnings()                 Past PR patterns        │
│  └─ format_review_context()            Format context          │
│                                                                  │
│  File Operations:                                               │
│  ├─ file_reader_tool(path)             Read files              │
│  ├─ file_writer_tool(path, content)    Write files             │
│  ├─ list_files_tool(dir)               List directory          │
│  └─ search_in_file_tool(file, query)   Search in file          │
│                                                                  │
│  Git Operations:                                                │
│  ├─ git_clone_tool(repo_url)           Clone repository        │
│  ├─ git_get_pr_files(pr)               Get changed files       │
│  ├─ git_get_pr_diff(pr)                Get diff                │
│  └─ git_get_file_content(path)         Get file content        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Recursive Analysis Loop Detail

```
┌──────────────────────────────────────────────────────────────┐
│            Recursive Analysis: main.py                        │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Iteration 1: Initial Scan                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Read code                                        │    │
│  │    file_reader_tool("main.py")                      │    │
│  │    → See function at line 42                        │    │
│  │                                                      │    │
│  │ 2. Read reports                                     │    │
│  │    read_parser_reports("main.py")                   │    │
│  │    → AST: function complexity = 25                  │    │
│  │    → CFG: cyclomatic complexity = 25                │    │
│  │                                                      │    │
│  │ 3. Find issue                                       │    │
│  │    → High complexity at line 42                     │    │
│  │                                                      │    │
│  │ 4. Continue? YES (need more analysis)               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  Iteration 2: Deeper Analysis                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Focus on line 42 area                            │    │
│  │    → Check surrounding code                         │    │
│  │                                                      │    │
│  │ 2. Check specific issues                            │    │
│  │    check_specific_issue_in_reports(                 │    │
│  │        "main.py",                                    │    │
│  │        "unreachable_code",                          │    │
│  │        line_number=50                               │    │
│  │    )                                                 │    │
│  │    → Confirmed: unreachable code at line 50         │    │
│  │                                                      │    │
│  │ 3. Find more issues                                 │    │
│  │    → Unreachable code at line 50                    │    │
│  │                                                      │    │
│  │ 4. Continue? YES (check dependencies)               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  Iteration 3: Dependency Analysis                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Read PDG section                                 │    │
│  │    reports['pdg']['data_dependencies']              │    │
│  │    → 45 data dependencies!                          │    │
│  │                                                      │    │
│  │ 2. Find issue                                       │    │
│  │    → Complex dependencies                           │    │
│  │                                                      │    │
│  │ 3. Continue? NO (analysis complete)                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  Total Issues Found: 3                                       │
│  Next Stage: Validation                                      │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

## Knowledge Base Validation Flow

```
Issues Found: [Issue #1, Issue #2, Issue #3]
     │
     ▼
For each issue:
     │
     ├─→ Issue #1: High Complexity (line 42)
     │   ├─→ search_knowledge_base("high complexity main.py")
     │   ├─→ Result: No past acceptance found
     │   ├─→ Decision: ✅ KEEP (valid issue)
     │   └─→ Add to validated_issues
     │
     ├─→ Issue #2: Unreachable Code (line 50)
     │   ├─→ search_knowledge_base("unreachable code")
     │   ├─→ Result: No past acceptance
     │   ├─→ Decision: ✅ KEEP (valid issue)
     │   └─→ Add to validated_issues
     │
     └─→ Issue #3: Missing Docs (line 45)
         ├─→ search_knowledge_base("documentation")
         ├─→ Result: "Team doesn't require docstrings for utils"
         ├─→ Decision: ❌ FILTER OUT
         └─→ Skip this issue

Validated Issues: [Issue #1, Issue #2]
     │
     ▼
Prepare Comments
```

## File Processing Queue

```
Initial Queue: ["main.py", "utils.py", "models.py"]

┌────────────────────────────────────────────────────┐
│  Process main.py                                   │
│  ├─→ Generate reports                              │
│  ├─→ Analyze (10 iterations max)                   │
│  ├─→ Validate (2 valid issues)                     │
│  └─→ Comments prepared: 2                          │
└────────────────────────────────────────────────────┘
     │
     ▼
Queue: ["utils.py", "models.py"]

┌────────────────────────────────────────────────────┐
│  Process utils.py                                  │
│  ├─→ Generate reports                              │
│  ├─→ Analyze (5 iterations)                        │
│  ├─→ Validate (1 valid issue)                      │
│  └─→ Comments prepared: 1                          │
└────────────────────────────────────────────────────┘
     │
     ▼
Queue: ["models.py"]

┌────────────────────────────────────────────────────┐
│  Process models.py                                 │
│  ├─→ Generate reports                              │
│  ├─→ Analyze (3 iterations)                        │
│  ├─→ Validate (0 valid issues)                     │
│  └─→ Comments prepared: 0                          │
└────────────────────────────────────────────────────┘
     │
     ▼
Queue: [] (empty)

Finalize: Total 3 comments across 2 files
```

## Output Structure

```json
{
  "status": "success",
  "stage": "complete",
  "pr_context": {
    "repo_url": "owner/repo",
    "pr_number": 123,
    "branch": "feature/awesome"
  },
  "files_analyzed": {
    "main.py": {
      "iterations": 3,
      "issues_found": 3,
      "validated_issues": 2
    },
    "utils.py": {
      "iterations": 5,
      "issues_found": 2,
      "validated_issues": 1
    },
    "models.py": {
      "iterations": 3,
      "issues_found": 1,
      "validated_issues": 0
    }
  },
  "total_issues_found": 6,
  "validated_issues_count": 3,
  "comments_count": 3,
  "comments": [
    {
      "path": "main.py",
      "line": 42,
      "body": "Function has high cyclomatic complexity (25)..."
    },
    {
      "path": "main.py",
      "line": 50,
      "body": "Unreachable code detected..."
    },
    {
      "path": "utils.py",
      "line": 100,
      "body": "Consider refactoring..."
    }
  ]
}
```

## System Characteristics

```
┌─────────────────────────────────────────────────────┐
│  Performance Profile                                 │
├─────────────────────────────────────────────────────┤
│  Per File:                                          │
│  ├─ Report Generation: 5-10s                        │
│  ├─ Analysis (avg 3 iterations): 6-15s              │
│  ├─ KB Validation: 1-2s                             │
│  └─ Total: ~15-30s per file                         │
│                                                      │
│  Typical PR (3 files):                              │
│  └─ Total Time: 45-90s                              │
├─────────────────────────────────────────────────────┤
│  Quality Metrics                                     │
├─────────────────────────────────────────────────────┤
│  ├─ Issue Detection Rate: High                      │
│  ├─ False Positive Rate: Low (KB filtered)          │
│  ├─ Evidence Quality: High (parser-backed)          │
│  └─ Maintainer Satisfaction: High (relevant only)   │
└─────────────────────────────────────────────────────┘
```

This completes your CodeRabbit-like implementation! 🎉

