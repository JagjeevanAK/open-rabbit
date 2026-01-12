"""
Parser Agent Output Schemas

Defines structured output types for the Parser Agent which handles:
- AST parsing and summarization
- Semantic graph construction
- Symbol extraction
- Call graph building
- Hotspot detection (complexity analysis)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any


class SymbolType(str, Enum):
    """Types of code symbols that can be extracted."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    IMPORT = "import"
    EXPORT = "export"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    DECORATOR = "decorator"


@dataclass
class FileMetadata:
    """
    Metadata about a parsed file.
    
    Contains high-level information about the file structure
    without the full content.
    """
    path: str
    language: str
    line_count: int
    function_count: int
    class_count: int
    import_count: int
    export_count: int
    complexity_score: float  # Average complexity across functions
    has_tests: bool = False
    
    # Optional detailed summaries
    summary: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "language": self.language,
            "line_count": self.line_count,
            "function_count": self.function_count,
            "class_count": self.class_count,
            "import_count": self.import_count,
            "export_count": self.export_count,
            "complexity_score": self.complexity_score,
            "has_tests": self.has_tests,
            "summary": self.summary,
        }


@dataclass
class Symbol:
    """
    A code symbol extracted from parsing.
    
    Represents functions, classes, variables, imports, etc.
    """
    name: str
    symbol_type: SymbolType
    file_path: str
    start_line: int
    end_line: Optional[int] = None
    scope: Optional[str] = None  # e.g., "global", "class:MyClass"
    signature: Optional[str] = None  # For functions/methods
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    complexity: Optional[int] = None
    modifiers: List[str] = field(default_factory=list)  # public, private, async, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "symbol_type": self.symbol_type.value,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "scope": self.scope,
            "signature": self.signature,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "docstring": self.docstring,
            "complexity": self.complexity,
            "modifiers": self.modifiers,
        }


@dataclass
class CallGraphEntry:
    """
    An entry in the call graph showing function relationships.
    """
    caller: str  # Full path: "file.py:function_name" or "file.py:ClassName.method"
    caller_file: str
    caller_line: int
    callees: List[str] = field(default_factory=list)  # List of called function names
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "caller": self.caller,
            "caller_file": self.caller_file,
            "caller_line": self.caller_line,
            "callees": self.callees,
        }


@dataclass
class Hotspot:
    """
    A code hotspot indicating potential complexity or issues.
    
    Detected based on:
    - High cyclomatic complexity (> 10)
    - Large function size
    - Deep nesting
    - Many parameters
    """
    file_path: str
    symbol_name: str
    start_line: int
    end_line: Optional[int]
    hotspot_type: str  # "high_complexity", "large_function", "deep_nesting", "many_params"
    severity: str  # "warning", "critical"
    metric_value: float  # The actual measured value
    threshold: float  # The threshold that was exceeded
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "symbol_name": self.symbol_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "hotspot_type": self.hotspot_type,
            "severity": self.severity,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "message": self.message,
        }


@dataclass
class ParserOutput:
    """
    Complete output from the Parser Agent.
    
    This is the structured metadata returned after parsing,
    NOT prose or review comments.
    
    Example:
    {
        "files": [...],
        "symbols": [...],
        "call_graph": {...},
        "hotspots": [...]
    }
    """
    files: List[FileMetadata] = field(default_factory=list)
    symbols: List[Symbol] = field(default_factory=list)
    call_graph: List[CallGraphEntry] = field(default_factory=list)
    hotspots: List[Hotspot] = field(default_factory=list)
    
    # Raw reports for downstream agents
    ast_reports: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # file_path -> ast_report
    semantic_reports: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # file_path -> semantic_report
    
    # Parsing errors (non-fatal)
    errors: List[Dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "files": [f.to_dict() for f in self.files],
            "symbols": [s.to_dict() for s in self.symbols],
            "call_graph": [c.to_dict() for c in self.call_graph],
            "hotspots": [h.to_dict() for h in self.hotspots],
            "ast_reports": self.ast_reports,
            "semantic_reports": self.semantic_reports,
            "errors": self.errors,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParserOutput":
        """Reconstruct ParserOutput from dictionary (for checkpointing)."""
        return cls(
            files=[
                FileMetadata(
                    path=f["path"],
                    language=f["language"],
                    line_count=f["line_count"],
                    function_count=f["function_count"],
                    class_count=f["class_count"],
                    import_count=f["import_count"],
                    export_count=f["export_count"],
                    complexity_score=f["complexity_score"],
                    has_tests=f.get("has_tests", False),
                    summary=f.get("summary"),
                )
                for f in data.get("files", [])
            ],
            symbols=[
                Symbol(
                    name=s["name"],
                    symbol_type=SymbolType(s["symbol_type"]),
                    file_path=s["file_path"],
                    start_line=s["start_line"],
                    end_line=s.get("end_line"),
                    scope=s.get("scope"),
                    signature=s.get("signature"),
                    parameters=s.get("parameters", []),
                    return_type=s.get("return_type"),
                    docstring=s.get("docstring"),
                    complexity=s.get("complexity"),
                    modifiers=s.get("modifiers", []),
                )
                for s in data.get("symbols", [])
            ],
            call_graph=[
                CallGraphEntry(
                    caller=c["caller"],
                    caller_file=c["caller_file"],
                    caller_line=c["caller_line"],
                    callees=c.get("callees", []),
                )
                for c in data.get("call_graph", [])
            ],
            hotspots=[
                Hotspot(
                    file_path=h["file_path"],
                    symbol_name=h["symbol_name"],
                    start_line=h["start_line"],
                    end_line=h.get("end_line"),
                    hotspot_type=h["hotspot_type"],
                    severity=h["severity"],
                    metric_value=h["metric_value"],
                    threshold=h["threshold"],
                    message=h["message"],
                )
                for h in data.get("hotspots", [])
            ],
            ast_reports=data.get("ast_reports", {}),
            semantic_reports=data.get("semantic_reports", {}),
            errors=data.get("errors", []),
        )
    
    def get_symbols_by_file(self, file_path: str) -> List[Symbol]:
        """Get all symbols for a specific file."""
        return [s for s in self.symbols if s.file_path == file_path]
    
    def get_functions(self) -> List[Symbol]:
        """Get all function symbols."""
        return [s for s in self.symbols if s.symbol_type in (SymbolType.FUNCTION, SymbolType.METHOD)]
    
    def get_classes(self) -> List[Symbol]:
        """Get all class symbols."""
        return [s for s in self.symbols if s.symbol_type == SymbolType.CLASS]
    
    def get_high_complexity_functions(self, threshold: int = 10) -> List[Symbol]:
        """Get functions with complexity above threshold."""
        return [
            s for s in self.get_functions()
            if s.complexity is not None and s.complexity > threshold
        ]
