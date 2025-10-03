# Code Analysis Pipeline

A modular source code analysis pipeline that transforms code into Abstract Syntax Trees (AST), Control Flow Graphs (CFG), and Program Dependence Graphs (PDG). Built with tree-sitter for multi-language support.

## Features

- **Multi-language Support**: Python, JavaScript, TypeScript, and TSX
- **Three-Level Analysis**: AST → CFG → PDG transformation pipeline
- **Automatic Language Detection**: Detects language from file extensions
- **Modular Architecture**: Separate modules for parsing, control flow, and dependency analysis
- **Flexible API**: Run full pipeline or individual analysis steps

## Supported Languages

| Language   | File Extensions |
|------------|-----------------|
| Python     | `.py`           |
| JavaScript | `.js`, `.jsx`   |
| TypeScript | `.ts`           |
| TSX        | `.tsx`          |

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd Parsers

# Install dependencies using uv
uv sync
```

## Quick Start

### Basic Usage

```python
from pipeline import AnalysisPipeline

# Initialize pipeline
pipeline = AnalysisPipeline("python")

# Analyze code
code = """
def add(a, b):
    return a + b

result = add(5, 3)
"""

results = pipeline.run_full_pipeline(code)
print(f"AST Root: {results['ast']['root_type']}")
print(f"CFG Blocks: {len(results['cfg']['blocks'])}")
print(f"PDG Nodes: {len(results['pdg']['nodes'])}")
```

### Analyze from File

```python
pipeline = AnalysisPipeline()  # Auto-detect language

# Analyze file
results = pipeline.run_full_pipeline_from_file("script.py")

# Export results
pipeline.export_to_file("analysis_results.json")
```

### Step-by-Step Analysis

```python
pipeline = AnalysisPipeline("javascript")

# Step 1: Parse AST
ast_tree = pipeline.parse_ast(code)

# Step 2: Build CFG
cfg = pipeline.build_cfg()

# Step 3: Build PDG
pdg = pipeline.build_pdg()

# Access results
print(f"CFG has {len(cfg.blocks)} blocks")
print(f"PDG tracks {len(pdg.variables)} variables")
```

## Architecture

### Pipeline Flow

```
Source Code
    ↓
AST Parser (tree-sitter)
    ↓
CFG Builder (control flow analysis)
    ↓
PDG Builder (dependency analysis)
    ↓
Structured Output (JSON)
```

### Module Structure

```
Parsers/
├── pipeline.py              # Main orchestrator
├── ast_module/
│   └── ast_parser.py       # AST parsing with tree-sitter
├── cfg/
│   └── cfg_builder.py      # Control flow graph construction
├── pdg/
│   └── pdg_builder.py      # Program dependence graph construction
└── examples.py             # Usage examples
```

## Output Format

The pipeline produces structured JSON output with three main sections:

### AST Output
- Root node type
- Full syntax tree structure
- Source code positions

### CFG Output
- Basic blocks with unique IDs
- Block types (entry, exit, statement, condition, loop)
- Successor and predecessor relationships
- Statement mapping

### PDG Output
- Nodes with dependencies
- Data dependencies (variable definitions and uses)
- Control dependencies (conditional execution)
- Variable tracking across scopes

## Use Cases

- **Static Analysis**: Detect code patterns, vulnerabilities, and bugs
- **Code Review**: Automated review suggestions based on control and data flow
- **Refactoring**: Identify safe refactoring opportunities
- **AI-Assisted Development**: Feed structured code representation to AI models
- **Educational Tools**: Visualize code execution and dependencies

## API Reference

### AnalysisPipeline

#### Constructor
```python
AnalysisPipeline(language: Optional[str] = None)
```
Initialize pipeline with optional language specification. If `None`, language is auto-detected from file extensions.

#### Methods

**`run_full_pipeline(code: str) -> Dict`**  
Execute complete AST → CFG → PDG analysis on code string.

**`run_full_pipeline_from_file(file_path: str) -> Dict`**  
Execute complete analysis on a source file.

**`parse_ast(code: Union[str, bytes]) -> tree_sitter.Tree`**  
Parse code into Abstract Syntax Tree.

**`build_cfg() -> ControlFlowGraph`**  
Build Control Flow Graph from parsed AST.

**`build_pdg() -> ProgramDependenceGraph`**  
Build Program Dependence Graph from CFG.

**`get_summary() -> Dict`**  
Get summary statistics of all analysis components.

**`export_to_file(output_path: str, pretty: bool = True) -> None`**  
Export analysis results to JSON file.

## Dependencies

- `tree-sitter` >= 0.25.2
- `tree-sitter-python` >= 0.23.0
- `tree-sitter-javascript` >= 0.23.0
- `tree-sitter-typescript` >= 0.23.0

## Examples

See `examples.py` for comprehensive demonstrations including:
- Basic usage patterns
- Step-by-step analysis
- File analysis
- Multi-language support
- Error handling
- Export functionality

Run examples:
```bash
python examples.py
```

## Documentation

For detailed implementation details and architecture documentation, see `IMPLEMENTATION_GUIDE.md`.

## Requirements

- Python >= 3.13
- Compatible with macOS, Linux, and Windows

## License

See LICENSE file for details.

## Contributing

Contributions are welcome. Please ensure:
- Code follows existing architecture patterns
- New features include usage examples
- Tests pass for all supported languages
- Documentation is updated accordingly
