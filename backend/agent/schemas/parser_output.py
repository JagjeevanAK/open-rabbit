"""
Parser Agent Output Schemas

Defines the output structures for the Parser Agent including:
- AST analysis results
- Semantic graph summaries
- Security issues
- Dead code detection
- Complexity metrics
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

from .common import Severity, IssueCategory, ReviewIssue, FileChange


class SecurityIssueType(str, Enum):
    """Types of security issues"""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    COMMAND_INJECTION = "command_injection"
    PATH_TRAVERSAL = "path_traversal"
    HARDCODED_SECRET = "hardcoded_secret"
    INSECURE_RANDOM = "insecure_random"
    WEAK_CRYPTO = "weak_crypto"
    UNSAFE_DESERIALIZATION = "unsafe_deserialization"
    SSRF = "ssrf"
    XXE = "xxe"
    OPEN_REDIRECT = "open_redirect"
    SENSITIVE_DATA_EXPOSURE = "sensitive_data_exposure"
    INSECURE_DEPENDENCY = "insecure_dependency"
    DEBUG_ENABLED = "debug_enabled"
    OTHER = "other"


class DeadCodeType(str, Enum):
    """Types of dead/unused code"""
    UNUSED_VARIABLE = "unused_variable"
    UNUSED_FUNCTION = "unused_function"
    UNUSED_IMPORT = "unused_import"
    UNUSED_PARAMETER = "unused_parameter"
    UNUSED_CLASS = "unused_class"
    UNREACHABLE_CODE = "unreachable_code"


class FunctionInfo(BaseModel):
    """Information about a function/method"""
    name: str
    start_line: int
    end_line: int
    complexity: int = Field(default=1, description="Cyclomatic complexity")
    parameters: List[str] = Field(default_factory=list)
    return_type: Optional[str] = None
    has_docstring: bool = False
    is_async: bool = False
    is_generator: bool = False
    is_exported: bool = False
    decorators: List[str] = Field(default_factory=list)
    calls: List[str] = Field(default_factory=list, description="Functions this function calls")


class ClassInfo(BaseModel):
    """Information about a class"""
    name: str
    start_line: int
    end_line: int
    methods: List[str] = Field(default_factory=list)
    inherits_from: List[str] = Field(default_factory=list)
    has_docstring: bool = False
    is_exported: bool = False
    decorators: List[str] = Field(default_factory=list)
    properties: List[str] = Field(default_factory=list)


class VariableInfo(BaseModel):
    """Information about a variable"""
    name: str
    line: int
    scope: str = "global"
    is_used: bool = True
    is_exported: bool = False
    type_annotation: Optional[str] = None
    declaration_count: int = 1
    usage_count: int = 0
    usage_lines: List[int] = Field(default_factory=list)


class ImportInfo(BaseModel):
    """Information about an import statement"""
    module: str
    items: List[str] = Field(default_factory=list, description="Imported items, empty for module import")
    alias: Optional[str] = None
    line: int
    is_used: bool = True


class SecurityIssue(BaseModel):
    """A security issue found by static analysis"""
    type: SecurityIssueType
    severity: Severity
    line: int
    column: Optional[int] = None
    description: str
    recommendation: str
    code_snippet: Optional[str] = None
    cwe_id: Optional[str] = Field(default=None, description="CWE identifier if applicable")
    
    def to_review_issue(self, file_path: str) -> ReviewIssue:
        """Convert to ReviewIssue format"""
        return ReviewIssue(
            file_path=file_path,
            line_start=self.line,
            severity=self.severity,
            category=IssueCategory.SECURITY,
            title=f"Security: {self.type.value.replace('_', ' ').title()}",
            message=self.description,
            suggestion=self.recommendation,
            code_snippet=self.code_snippet,
            confidence=0.9,
            source="parser"
        )


class SecurityPattern(BaseModel):
    """Pattern for detecting security issues"""
    type: SecurityIssueType
    severity: Severity
    pattern: str = Field(..., description="Regex pattern to match")
    description: str
    recommendation: str
    languages: List[str] = Field(default_factory=lambda: ["python", "javascript", "typescript"])
    cwe_id: Optional[str] = None


class DeadCodeInfo(BaseModel):
    """Information about dead/unused code"""
    type: DeadCodeType
    name: str
    line: int
    scope: str = "global"
    
    def to_review_issue(self, file_path: str) -> ReviewIssue:
        """Convert to ReviewIssue format"""
        type_label = self.type.value.replace("_", " ")
        return ReviewIssue(
            file_path=file_path,
            line_start=self.line,
            severity=Severity.LOW,
            category=IssueCategory.DEAD_CODE,
            title=f"Unused: {type_label}",
            message=f"'{self.name}' appears to be unused and can be removed.",
            suggestion=f"Remove the unused {type_label} '{self.name}' to improve code clarity.",
            confidence=0.7,
            source="parser"
        )


class ComplexityIssue(BaseModel):
    """High complexity warning"""
    function_name: str
    line: int
    complexity: int
    threshold: int = 10
    
    def to_review_issue(self, file_path: str) -> ReviewIssue:
        """Convert to ReviewIssue format"""
        severity = Severity.HIGH if self.complexity > 20 else Severity.MEDIUM
        return ReviewIssue(
            file_path=file_path,
            line_start=self.line,
            severity=severity,
            category=IssueCategory.COMPLEXITY,
            title=f"High Complexity: {self.function_name}",
            message=f"Function '{self.function_name}' has cyclomatic complexity of {self.complexity} (threshold: {self.threshold}).",
            suggestion="Consider breaking this function into smaller, more focused functions.",
            confidence=0.95,
            source="parser"
        )


class ParserInput(BaseModel):
    """Input to the Parser Agent"""
    changed_files: List[FileChange]
    repo_path: str = Field(..., description="Path to the cloned repository")
    
    # Configuration
    complexity_threshold: int = Field(default=10)
    enable_security_scan: bool = Field(default=True)
    enable_dead_code_detection: bool = Field(default=True)


class FileAnalysis(BaseModel):
    """Analysis results for a single file"""
    file_path: str
    language: str
    total_lines: int
    code_lines: int
    
    # AST Analysis
    functions: List[FunctionInfo] = Field(default_factory=list)
    classes: List[ClassInfo] = Field(default_factory=list)
    imports: List[ImportInfo] = Field(default_factory=list)
    variables: List[VariableInfo] = Field(default_factory=list)
    
    # Semantic Analysis
    call_graph: Dict[str, List[str]] = Field(default_factory=dict)
    inheritance_graph: Dict[str, List[str]] = Field(default_factory=dict)
    
    # Issues
    security_issues: List[SecurityIssue] = Field(default_factory=list)
    dead_code: List[DeadCodeInfo] = Field(default_factory=list)
    complexity_issues: List[ComplexityIssue] = Field(default_factory=list)
    
    # Metrics
    avg_complexity: float = Field(default=0.0)
    max_complexity: int = Field(default=0)
    
    # Errors during parsing
    parse_error: Optional[str] = None


class ParserOutput(BaseModel):
    """Output from the Parser Agent"""
    files: List[FileAnalysis] = Field(default_factory=list)
    
    # Aggregated stats
    total_files: int = Field(default=0)
    total_functions: int = Field(default=0)
    total_classes: int = Field(default=0)
    total_security_issues: int = Field(default=0)
    total_dead_code: int = Field(default=0)
    total_complexity_issues: int = Field(default=0)
    
    # Overall metrics
    avg_complexity: float = Field(default=0.0)
    files_with_issues: int = Field(default=0)
    
    # Errors
    failed_files: List[str] = Field(default_factory=list)
    
    def get_all_issues(self) -> List[ReviewIssue]:
        """Get all issues as ReviewIssue objects"""
        issues = []
        for file_analysis in self.files:
            # Security issues
            for sec in file_analysis.security_issues:
                issues.append(sec.to_review_issue(file_analysis.file_path))
            # Dead code
            for dead in file_analysis.dead_code:
                issues.append(dead.to_review_issue(file_analysis.file_path))
            # Complexity issues
            for comp in file_analysis.complexity_issues:
                issues.append(comp.to_review_issue(file_analysis.file_path))
        return issues
    
    def get_file_analysis(self, file_path: str) -> Optional[FileAnalysis]:
        """Get analysis for a specific file"""
        for f in self.files:
            if f.file_path == file_path:
                return f
        return None
