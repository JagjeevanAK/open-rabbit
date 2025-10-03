# Complete Implementation Guide - AST → CFG → PDG Pipeline

This document explains **how everything is implemented** in the code analysis pipeline.

---

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Module 1: AST Parser](#module-1-ast-parser)
4. [Module 2: CFG Builder](#module-2-cfg-builder)
5. [Module 3: PDG Builder](#module-3-pdg-builder)
6. [Module 4: Pipeline Orchestrator](#module-4-pipeline-orchestrator)
7. [How Auto-Detection Works](#how-auto-detection-works)
8. [Data Flow](#data-flow)
9. [Usage Examples](#usage-examples)
10. [Implementation Details](#implementation-details)

---

## Overview

This pipeline transforms source code into three levels of representation:

```
Source Code → AST (Abstract Syntax Tree)
           → CFG (Control Flow Graph)
           → PDG (Program Dependence Graph)
```

### Purpose
- **AST**: Understand code structure (functions, classes, expressions)
- **CFG**: Analyze execution flow (branches, loops, control flow)
- **PDG**: Track dependencies (variable usage, data flow)

### Use Case
Feed structured analysis to AI for intelligent code review, bug detection, and refactoring suggestions.

---

## Architecture

### Directory Structure
```
Parsers/
├── ast_module/
│   ├── __init__.py          # Exports parse_code, parse_file
│   └── ast_parser.py        # Tree-sitter parser implementation
│
├── cfg/
│   ├── __init__.py          # Exports build_cfg_from_ast
│   └── cfg_builder.py       # Control flow graph builder
│
├── pdg/
│   ├── __init__.py          # Exports build_pdg_from_cfg
│   └── pdg_builder.py       # Program dependence graph builder
│
├── pipeline.py              # Main orchestrator with auto-detection
├── examples.py              # Usage examples
└── README.md                # User documentation
```

### Design Principles
1. **Separation of Concerns**: Each module handles one transformation
2. **Modularity**: Can use AST, CFG, or PDG independently
3. **Type Safety**: Full type hints throughout
4. **Extensibility**: Easy to add new languages or analysis types

---

## Module 1: AST Parser

**File**: `ast_module/ast_parser.py`

### What It Does
Parses source code into an Abstract Syntax Tree using Tree-sitter parsers.

### Implementation

#### 1. Parser Setup
```python
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

# Initialize parsers for each language
PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())
TS_LANGUAGE = Language(tstypescript.language_typescript())
TSX_LANGUAGE = Language(tstypescript.language_tsx())

parsers = {
    "python": PY_LANGUAGE,
    "javascript": JS_LANGUAGE,
    "typescript": TS_LANGUAGE,
    "tsx": TSX_LANGUAGE,
}
```

**Why Tree-sitter?**
- Industry-standard parser (used by GitHub, Atom, Neovim)
- Handles syntax errors gracefully
- Fast (parses millions of lines per second)
- Supports incremental parsing

#### 2. Core Functions

**`parse_code(code, language)`**
```python
def parse_code(code: Union[str, bytes], language: str) -> Tree:
    """Parse source code string into AST"""
    parser = Parser(parsers[language])
    
    # Handle both string and bytes
    if isinstance(code, str):
        code = bytes(code, "utf8")
    
    tree = parser.parse(code)
    return tree
```

**`parse_file(file_path, language)`**
```python
def parse_file(file_path: str, language: str) -> Tree:
    """Parse source file into AST"""
    with open(file_path, "rb") as f:
        code = f.read()
    return parse_code(code, language)
```

### How It Works

1. **Input**: Source code (string or file path) + language
2. **Processing**: Tree-sitter tokenizes and parses the code
3. **Output**: AST Tree object with root node

**AST Structure**:
```python
tree.root_node
├── type: "module" (Python) or "program" (JS/TS)
├── children: [node1, node2, ...]
└── text: bytes of source code
```

Each node has:
- `type`: Node type (function_definition, if_statement, etc.)
- `children`: Child nodes
- `start_point`, `end_point`: Position in source
- `text`: Source code bytes for this node

---

## Module 2: CFG Builder

**File**: `cfg/cfg_builder.py`

### What It Does
Builds a Control Flow Graph showing all possible execution paths through code.

### Key Concepts

#### Block Types
```python
class BlockType(Enum):
    ENTRY = "entry"              # Program entry point
    EXIT = "exit"                # Program exit point
    STATEMENT = "statement"      # Normal statement
    CONDITION = "condition"      # If/else branch point
    LOOP_HEADER = "loop_header"  # Loop condition check
    LOOP_BODY = "loop_body"      # Loop body
    FUNCTION = "function"        # Function definition
    RETURN = "return"            # Return statement
    EXCEPTION = "exception"      # Try/except
```

#### BasicBlock Class
```python
@dataclass
class BasicBlock:
    id: int                      # Unique identifier
    type: BlockType              # Type of block
    statements: List[str]        # Code statements
    successors: List[int]        # Next block IDs
    predecessors: List[int]      # Previous block IDs
```

### Implementation

#### CFGBuilder Class
```python
class CFGBuilder:
    def __init__(self):
        self.blocks: Dict[int, BasicBlock] = {}
        self.next_block_id = 0
        self.entry_block_id = None
        self.exit_block_id = None
```

#### Core Algorithm

**`build_cfg_from_ast(root_node, language)`**
```python
def build_cfg_from_ast(root_node, language: str) -> ControlFlowGraph:
    builder = CFGBuilder()
    
    # 1. Create entry block
    entry = builder._create_block(BlockType.ENTRY)
    builder.entry_block_id = entry.id
    
    # 2. Create exit block
    exit_block = builder._create_block(BlockType.EXIT)
    builder.exit_block_id = exit_block.id
    
    # 3. Process AST nodes recursively
    last_block = builder._process_node(
        root_node, 
        entry, 
        exit_block,
        None  # break target
    )
    
    # 4. Connect last block to exit
    if last_block:
        builder._add_edge(last_block, exit_block)
    
    return ControlFlowGraph(...)
```

#### Processing Different Node Types

**1. Sequential Statements**
```python
def _process_node(self, node, current_block, exit_block, break_target):
    # For each child node, process sequentially
    for child in node.children:
        if child.type == "if_statement":
            current_block = self._process_if_statement(...)
        elif child.type in ["for_statement", "while_statement"]:
            current_block = self._process_loop(...)
        else:
            # Add statement to current block
            current_block.statements.append(child.text.decode())
```

**2. If/Else Statements**
```python
def _process_if_statement(self, node, current_block, exit_block, break_target):
    # Create condition block
    cond_block = self._create_block(BlockType.CONDITION)
    self._add_edge(current_block, cond_block)
    
    # Create merge block (where branches converge)
    merge_block = self._create_block(BlockType.STATEMENT)
    
    # Process 'then' branch
    then_block = self._create_block(BlockType.STATEMENT)
    self._add_edge(cond_block, then_block)
    then_last = self._process_node(then_body, then_block, exit_block, break_target)
    if then_last:
        self._add_edge(then_last, merge_block)
    
    # Process 'else' branch (if exists)
    if else_body:
        else_block = self._create_block(BlockType.STATEMENT)
        self._add_edge(cond_block, else_block)
        else_last = self._process_node(else_body, else_block, exit_block, break_target)
        if else_last:
            self._add_edge(else_last, merge_block)
    else:
        # No else: condition can go directly to merge
        self._add_edge(cond_block, merge_block)
    
    return merge_block
```

**3. Loops (For/While)**
```python
def _process_loop(self, node, current_block, exit_block, break_target):
    # Create loop header (condition check)
    header = self._create_block(BlockType.LOOP_HEADER)
    self._add_edge(current_block, header)
    
    # Create loop body
    body = self._create_block(BlockType.LOOP_BODY)
    self._add_edge(header, body)
    
    # Create after-loop block
    after_loop = self._create_block(BlockType.STATEMENT)
    
    # Process loop body (pass after_loop as break target)
    body_last = self._process_node(
        loop_body, 
        body, 
        exit_block,
        after_loop  # break jumps here
    )
    
    # Loop back to header
    if body_last:
        self._add_edge(body_last, header)
    
    # Exit loop (condition false)
    self._add_edge(header, after_loop)
    
    return after_loop
```

**4. Functions**
```python
def _process_function(self, node, current_block, exit_block, break_target):
    func_block = self._create_block(BlockType.FUNCTION)
    self._add_edge(current_block, func_block)
    
    # Process function body
    func_last = self._process_node(
        function_body,
        func_block,
        exit_block,
        break_target
    )
    
    return func_last
```

### CFG Output Structure

```python
ControlFlowGraph:
    name: str                    # Graph name
    entry_block_id: int          # Entry block ID
    exit_block_id: int           # Exit block ID
    blocks: Dict[int, BasicBlock] # All blocks
    
    Methods:
        get_reachable_blocks(start)  # Find all reachable blocks
        to_json()                    # Export to JSON
        to_dot()                     # Export to Graphviz DOT
```

---

## Module 3: PDG Builder

**File**: `pdg/pdg_builder.py`

### What It Does
Builds a Program Dependence Graph tracking:
1. **Data Dependencies**: Variable definitions and uses
2. **Control Dependencies**: How control flow affects execution

### Key Concepts

#### Variable Tracking
```python
@dataclass
class Variable:
    name: str                    # Variable name
    scope: str                   # Scope (global, local, etc.)
    definition_nodes: List[int]  # Where defined
    use_nodes: List[int]         # Where used
```

#### PDG Node
```python
@dataclass
class PDGNode:
    id: int                      # Node ID
    statement: str               # Code statement
    defines: List[str]           # Variables defined
    uses: List[str]              # Variables used
    data_dependencies: List[int] # Nodes this depends on (data)
    control_dependencies: List[int] # Nodes this depends on (control)
```

### Implementation

#### PDGBuilder Class
```python
class PDGBuilder:
    def __init__(self):
        self.nodes: Dict[int, PDGNode] = {}
        self.variables: Dict[str, Variable] = {}
        self.cfg: Optional[ControlFlowGraph] = None
```

#### Core Algorithm

**`build_pdg_from_cfg(cfg, language)`**
```python
def build_pdg_from_cfg(cfg: ControlFlowGraph, language: str) -> ProgramDependenceGraph:
    builder = PDGBuilder()
    builder.cfg = cfg
    
    # 1. Create PDG nodes from CFG blocks
    for block_id, block in cfg.blocks.items():
        for stmt in block.statements:
            node = PDGNode(
                id=len(builder.nodes),
                statement=stmt,
                defines=[],
                uses=[],
                data_dependencies=[],
                control_dependencies=[]
            )
            builder.nodes[node.id] = node
    
    # 2. Extract variable definitions and uses
    builder._extract_variables()
    
    # 3. Compute data dependencies
    builder._compute_data_dependencies()
    
    # 4. Compute control dependencies
    builder._compute_control_dependencies()
    
    return ProgramDependenceGraph(...)
```

#### Variable Extraction

```python
def _extract_variables(self):
    """Extract variables from statements"""
    for node in self.nodes.values():
        stmt = node.statement
        
        # Pattern 1: Assignment (x = ...)
        if "=" in stmt and not any(op in stmt for op in ["==", "!=", ">=", "<="]):
            parts = stmt.split("=")
            var_name = parts[0].strip()
            node.defines.append(var_name)
            
            # Track in variables dict
            if var_name not in self.variables:
                self.variables[var_name] = Variable(
                    name=var_name,
                    scope="global",
                    definition_nodes=[],
                    use_nodes=[]
                )
            self.variables[var_name].definition_nodes.append(node.id)
        
        # Pattern 2: Variable uses
        # Extract identifiers from right side of assignments
        # and from expressions
        identifiers = self._extract_identifiers(stmt)
        for var_name in identifiers:
            node.uses.append(var_name)
            
            if var_name not in self.variables:
                self.variables[var_name] = Variable(
                    name=var_name,
                    scope="global",
                    definition_nodes=[],
                    use_nodes=[]
                )
            self.variables[var_name].use_nodes.append(node.id)
```

#### Data Dependencies

```python
def _compute_data_dependencies(self):
    """Compute data dependencies (def-use chains)"""
    for node in self.nodes.values():
        for used_var in node.uses:
            # Find where this variable was defined
            if used_var in self.variables:
                var = self.variables[used_var]
                # Add dependency on all definition nodes
                for def_node_id in var.definition_nodes:
                    if def_node_id != node.id:
                        node.data_dependencies.append(def_node_id)
```

**Example**:
```python
x = 5           # Node 0: defines x
y = x + 3       # Node 1: uses x, depends on Node 0
z = x * y       # Node 2: uses x and y, depends on Nodes 0 and 1
```

#### Control Dependencies

```python
def _compute_control_dependencies(self):
    """Compute control dependencies"""
    # Find all condition blocks in CFG
    for block_id, block in self.cfg.blocks.items():
        if block.type == BlockType.CONDITION:
            # All blocks in branches depend on this condition
            self._mark_control_dependent(block, block.successors)
```

**Example**:
```python
if x > 5:       # Condition block
    y = x + 1   # Depends on condition
else:
    y = x - 1   # Depends on condition
z = y           # No control dependency
```

### PDG Output Structure

```python
ProgramDependenceGraph:
    name: str
    entry_node: int
    nodes: Dict[int, PDGNode]
    variables: Dict[str, Variable]
    
    Methods:
        to_json()  # Export to JSON
        to_dot()   # Export to Graphviz DOT
```

---

## Module 4: Pipeline Orchestrator

**File**: `pipeline.py`

### What It Does
Orchestrates the complete AST → CFG → PDG pipeline with automatic language detection.

### Implementation

#### Extension Mapping
```python
EXTENSION_MAP = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',  # JSX is JavaScript
    '.ts': 'typescript',
    '.tsx': 'tsx'
}
```

#### AnalysisPipeline Class
```python
class AnalysisPipeline:
    def __init__(self, language: Optional[str] = None):
        self.language = language  # Can be None for auto-detect
        self.ast_tree = None
        self.cfg = None
        self.pdg = None
```

#### Auto-Detection
```python
@staticmethod
def detect_language_from_file(file_path: str) -> str:
    """Detect language from file extension"""
    path = Path(file_path)
    extension = path.suffix.lower()
    
    if extension not in EXTENSION_MAP:
        raise ValueError(f"Unsupported extension: {extension}")
    
    return EXTENSION_MAP[extension]
```

#### Complete Pipeline
```python
def run_pipeline_on_file(self, file_path: str) -> Dict[str, Any]:
    """Run complete analysis pipeline on a file"""
    
    # 1. Auto-detect language if not set
    if self.language is None:
        self.language = self.detect_language_from_file(file_path)
    
    # 2. Parse to AST
    self.parse_file(file_path)
    
    # 3. Build CFG from AST
    self.build_cfg()
    
    # 4. Build PDG from CFG
    self.build_pdg()
    
    # 5. Return all results
    return self.get_results()
```

---

## How Auto-Detection Works

### Step-by-Step Process

1. **User calls**: `pipeline.run_pipeline_on_file("script.py")`

2. **Extract extension**: 
   ```python
   extension = Path("script.py").suffix  # ".py"
   ```

3. **Lookup language**:
   ```python
   language = EXTENSION_MAP[".py"]  # "python"
   ```

4. **Set pipeline language**:
   ```python
   self.language = "python"
   ```

5. **Proceed with analysis** using detected language

### Supported Extensions
- `.py` → `python`
- `.js` → `javascript`
- `.jsx` → `javascript` (React JSX is JavaScript)
- `.ts` → `typescript`
- `.tsx` → `tsx` (React TypeScript)

---

## Data Flow

### Complete Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. INPUT: Source File (script.py)                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. AUTO-DETECT: Extract extension → Detect language        │
│    ".py" → "python"                                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. AST PARSING (ast_module/ast_parser.py)                  │
│    - Read file bytes                                        │
│    - Tree-sitter parse                                      │
│    - Output: AST Tree                                       │
│                                                             │
│    Tree Structure:                                          │
│    root (module)                                            │
│    ├── function_definition                                  │
│    │   ├── name: "calculate"                               │
│    │   ├── parameters                                       │
│    │   └── block                                            │
│    └── expression_statement                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. CFG BUILDING (cfg/cfg_builder.py)                       │
│    - Walk AST recursively                                   │
│    - Create BasicBlocks                                     │
│    - Connect with edges                                     │
│    - Output: ControlFlowGraph                               │
│                                                             │
│    CFG Structure:                                           │
│    Block 0 (entry) → Block 2 (statement)                    │
│                   → Block 3 (condition)                      │
│                      ├── Block 4 (then)                     │
│                      └── Block 5 (else)                     │
│                   → Block 6 (merge)                          │
│                   → Block 1 (exit)                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. PDG BUILDING (pdg/pdg_builder.py)                       │
│    - Extract variables from CFG blocks                      │
│    - Track definitions and uses                             │
│    - Compute data dependencies                              │
│    - Compute control dependencies                           │
│    - Output: ProgramDependenceGraph                         │
│                                                             │
│    PDG Structure:                                           │
│    Node 0: "x = 5"                                          │
│           defines: [x]                                      │
│    Node 1: "y = x + 3"                                      │
│           uses: [x]                                         │
│           data_deps: [0]                                    │
│    Node 2: "if x > y"                                       │
│           uses: [x, y]                                      │
│           data_deps: [0, 1]                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. OUTPUT: JSON/DOT Export                                  │
│    {                                                        │
│      "ast": {...},                                          │
│      "cfg": {                                               │
│        "blocks": {...},                                     │
│        "edges": [...]                                       │
│      },                                                     │
│      "pdg": {                                               │
│        "nodes": {...},                                      │
│        "variables": {...},                                  │
│        "dependencies": [...]                                │
│      }                                                      │
│    }                                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Usage Examples

### Example 1: Simple Analysis
```python
from pipeline import AnalysisPipeline

# Create pipeline (no language needed!)
pipeline = AnalysisPipeline()

# Analyze any file
results = pipeline.run_pipeline_on_file("script.py")

print(f"Language: {pipeline.language}")
print(f"CFG Blocks: {len(results['cfg']['blocks'])}")
print(f"Variables: {len(results['pdg']['variables'])}")
```

### Example 2: Step-by-Step
```python
pipeline = AnalysisPipeline()

# Step 1: Parse to AST
ast_tree = pipeline.parse_file("code.py")
print(f"AST root: {ast_tree.root_node.type}")

# Step 2: Build CFG
cfg = pipeline.build_cfg()
print(f"CFG blocks: {len(cfg.blocks)}")

# Step 3: Build PDG
pdg = pipeline.build_pdg()
print(f"PDG nodes: {len(pdg.nodes)}")
```

### Example 3: Batch Analysis
```python
import os
from pipeline import AnalysisPipeline

def analyze_project(project_dir):
    pipeline = AnalysisPipeline()
    
    for root, _, files in os.walk(project_dir):
        for file in files:
            if file.endswith(('.py', '.js', '.ts', '.tsx')):
                filepath = os.path.join(root, file)
                results = pipeline.run_pipeline_on_file(filepath)
                
                print(f"{file} ({pipeline.language}):")
                print(f"  Blocks: {len(results['cfg']['blocks'])}")
                print(f"  Variables: {len(results['pdg']['variables'])}")
```

---

## Implementation Details

### 1. Why Tree-sitter?
- **Robust**: Handles syntax errors gracefully
- **Fast**: Parses millions of lines per second
- **Incremental**: Can update parse tree efficiently
- **Production-Ready**: Used by GitHub for code analysis

### 2. CFG Algorithm Complexity
- **Time**: O(n) where n = number of AST nodes
- **Space**: O(b) where b = number of basic blocks
- **Worst Case**: Nested loops and conditionals create more blocks

### 3. PDG Variable Tracking
- Uses simple pattern matching for now
- Can be enhanced with symbol table analysis
- Tracks global scope (can be extended to local scopes)

### 4. Error Handling
```python
# Unsupported extension
try:
    pipeline = AnalysisPipeline()
    pipeline.run_pipeline_on_file("code.cpp")
except ValueError as e:
    print(f"Error: {e}")  # "Unsupported extension: .cpp"

# Missing language for direct code
try:
    pipeline = AnalysisPipeline()
    pipeline.parse_code("def hello(): pass")
except ValueError as e:
    print(f"Error: {e}")  # "No language specified"
```

### 5. Export Formats

**JSON Export**:
```python
pipeline.export_to_json("analysis.json")
```

**DOT Export** (for Graphviz):
```python
pipeline.export_visualizations("./output")
# Creates: output/cfg.dot and output/pdg.dot

# Convert to images:
# dot -Tpng output/cfg.dot -o cfg.png
```

---

## Summary

### What Each Module Does

1. **AST Parser** (`ast_module/`)
   - Parses source code using Tree-sitter
   - Outputs: Tree structure with nodes

2. **CFG Builder** (`cfg/`)
   - Walks AST to create control flow graph
   - Outputs: BasicBlocks connected by edges

3. **PDG Builder** (`pdg/`)
   - Analyzes CFG to find dependencies
   - Outputs: Nodes with data/control dependencies

4. **Pipeline** (`pipeline.py`)
   - Orchestrates all three stages
   - Adds auto-detection from file extensions
   - Provides simple API

### Key Algorithms

1. **AST Parsing**: Tree-sitter tokenization and parsing
2. **CFG Building**: Recursive AST traversal with block creation
3. **PDG Building**: Variable extraction + dependency analysis
4. **Auto-Detection**: Extension mapping lookup

### Design Decisions

1. **Modular**: Each stage independent
2. **Type-Safe**: Full type hints
3. **Extensible**: Easy to add new languages
4. **User-Friendly**: Auto-detection simplifies API

---

## Quick Start

```bash
# Install
uv sync

# Use
python examples.py  # See all features

# Your code
python -c "
from pipeline import AnalysisPipeline
pipeline = AnalysisPipeline()
results = pipeline.run_pipeline_on_file('yourfile.py')
print(results)
"
```

---

**That's how everything is implemented!** 🚀

The pipeline transforms source code through three stages (AST → CFG → PDG) to provide structured analysis data perfect for AI-powered code review.
