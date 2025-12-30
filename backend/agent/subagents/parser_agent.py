"""
Parser Agent

Performs static analysis on changed files:
- AST parsing
- Semantic graph construction
- Security vulnerability detection
- Dead code detection
- Complexity analysis

This agent runs first in the pipeline to gather structural information
about the code before LLM-based review.
"""

import re
import os
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.subagents.base_agent import BaseAgent
from agent.schemas.common import Severity, FileChange
from agent.schemas.parser_output import (
    ParserInput,
    ParserOutput,
    FileAnalysis,
    FunctionInfo,
    ClassInfo,
    VariableInfo,
    ImportInfo,
    SecurityIssue,
    SecurityIssueType,
    SecurityPattern,
    DeadCodeInfo,
    DeadCodeType,
    ComplexityIssue,
)
from agent.parsers import (
    AnalysisPipeline,
    EXTENSION_MAP,
    is_supported_language,
)


# Security patterns for common vulnerabilities
SECURITY_PATTERNS: List[SecurityPattern] = [
    # SQL Injection
    SecurityPattern(
        type=SecurityIssueType.SQL_INJECTION,
        severity=Severity.CRITICAL,
        pattern=r'(?:execute|cursor\.execute|query)\s*\(\s*["\'].*?%s|(?:f["\'].*?\{.*?["\'])|(?:["\'].*?\+.*?["\'])',
        description="Potential SQL injection vulnerability. User input may be directly concatenated into SQL query.",
        recommendation="Use parameterized queries or an ORM to prevent SQL injection.",
        languages=["python"],
        cwe_id="CWE-89"
    ),
    SecurityPattern(
        type=SecurityIssueType.SQL_INJECTION,
        severity=Severity.CRITICAL,
        pattern=r'(?:query|execute)\s*\(\s*`[^`]*\$\{',
        description="Potential SQL injection. Template literals with interpolation in SQL queries.",
        recommendation="Use parameterized queries instead of template literals for SQL.",
        languages=["javascript", "typescript"],
        cwe_id="CWE-89"
    ),
    
    # XSS
    SecurityPattern(
        type=SecurityIssueType.XSS,
        severity=Severity.HIGH,
        pattern=r'innerHTML\s*=|document\.write\s*\(|\.html\s*\(',
        description="Potential XSS vulnerability. Direct DOM manipulation with untrusted content.",
        recommendation="Use textContent instead of innerHTML, or sanitize HTML content before insertion.",
        languages=["javascript", "typescript", "tsx"],
        cwe_id="CWE-79"
    ),
    SecurityPattern(
        type=SecurityIssueType.XSS,
        severity=Severity.HIGH,
        pattern=r'dangerouslySetInnerHTML',
        description="React dangerouslySetInnerHTML can lead to XSS if content is not sanitized.",
        recommendation="Ensure content passed to dangerouslySetInnerHTML is properly sanitized.",
        languages=["javascript", "typescript", "tsx"],
        cwe_id="CWE-79"
    ),
    
    # Command Injection
    SecurityPattern(
        type=SecurityIssueType.COMMAND_INJECTION,
        severity=Severity.CRITICAL,
        pattern=r'(?:os\.system|subprocess\.call|subprocess\.run|subprocess\.Popen)\s*\([^)]*(?:f["\']|\+|%)',
        description="Potential command injection. User input may be passed to system commands.",
        recommendation="Use subprocess with shell=False and pass arguments as a list.",
        languages=["python"],
        cwe_id="CWE-78"
    ),
    SecurityPattern(
        type=SecurityIssueType.COMMAND_INJECTION,
        severity=Severity.CRITICAL,
        pattern=r'(?:exec|spawn|execSync)\s*\([^)]*(?:`|\+|\$\{)',
        description="Potential command injection vulnerability in shell command execution.",
        recommendation="Avoid shell command execution with user input. Use libraries instead.",
        languages=["javascript", "typescript"],
        cwe_id="CWE-78"
    ),
    
    # Hardcoded Secrets
    SecurityPattern(
        type=SecurityIssueType.HARDCODED_SECRET,
        severity=Severity.HIGH,
        pattern=r'(?:password|secret|api_key|apikey|api-key|token|auth)\s*=\s*["\'][^"\']{8,}["\']',
        description="Potential hardcoded secret or credential detected.",
        recommendation="Use environment variables or a secrets manager for sensitive values.",
        languages=["python", "javascript", "typescript"],
        cwe_id="CWE-798"
    ),
    SecurityPattern(
        type=SecurityIssueType.HARDCODED_SECRET,
        severity=Severity.HIGH,
        pattern=r'(?:AKIA|sk-|ghp_|gho_|github_pat_)[A-Za-z0-9]{10,}',
        description="Potential AWS key, OpenAI key, or GitHub token detected.",
        recommendation="Remove hardcoded credentials and use environment variables.",
        languages=["python", "javascript", "typescript"],
        cwe_id="CWE-798"
    ),
    
    # Path Traversal
    SecurityPattern(
        type=SecurityIssueType.PATH_TRAVERSAL,
        severity=Severity.HIGH,
        pattern=r'(?:open|read_file|write_file|Path)\s*\([^)]*(?:\+|f["\']|%)',
        description="Potential path traversal vulnerability. User input may be used in file paths.",
        recommendation="Validate and sanitize file paths. Use os.path.basename or Path.resolve().",
        languages=["python"],
        cwe_id="CWE-22"
    ),
    SecurityPattern(
        type=SecurityIssueType.PATH_TRAVERSAL,
        severity=Severity.HIGH,
        pattern=r'(?:readFile|writeFile|createReadStream)\s*\([^)]*(?:\+|`|\$\{)',
        description="Potential path traversal in file system operations.",
        recommendation="Validate file paths and use path.resolve() to prevent traversal.",
        languages=["javascript", "typescript"],
        cwe_id="CWE-22"
    ),
    
    # Insecure Random
    SecurityPattern(
        type=SecurityIssueType.INSECURE_RANDOM,
        severity=Severity.MEDIUM,
        pattern=r'(?:random\.random|random\.randint|Math\.random)\s*\(',
        description="Using non-cryptographic random number generator for potentially sensitive operation.",
        recommendation="Use secrets module (Python) or crypto.randomBytes (Node.js) for security-sensitive operations.",
        languages=["python", "javascript", "typescript"],
        cwe_id="CWE-330"
    ),
    
    # Debug Mode
    SecurityPattern(
        type=SecurityIssueType.DEBUG_ENABLED,
        severity=Severity.MEDIUM,
        pattern=r'(?:DEBUG\s*=\s*True|debug\s*:\s*true|\.debug\s*=\s*true)',
        description="Debug mode appears to be enabled. This may expose sensitive information.",
        recommendation="Ensure debug mode is disabled in production environments.",
        languages=["python", "javascript", "typescript"],
        cwe_id="CWE-215"
    ),
    
    # Eval Usage
    SecurityPattern(
        type=SecurityIssueType.COMMAND_INJECTION,
        severity=Severity.CRITICAL,
        pattern=r'\beval\s*\(',
        description="Use of eval() can lead to code injection vulnerabilities.",
        recommendation="Avoid eval(). Use safer alternatives like JSON.parse() or ast.literal_eval().",
        languages=["python", "javascript", "typescript"],
        cwe_id="CWE-95"
    ),
]


class ParserAgent(BaseAgent[ParserInput, ParserOutput]):
    """
    Parser Agent for static code analysis.
    
    Analyzes changed files to extract:
    - Structural information (functions, classes, imports)
    - Security vulnerabilities
    - Dead/unused code
    - Complexity metrics
    """
    
    def __init__(
        self,
        enable_checkpointing: bool = True,
        max_workers: int = 4,
        security_patterns: Optional[List[SecurityPattern]] = None
    ):
        """
        Initialize parser agent.
        
        Args:
            enable_checkpointing: Enable state checkpointing
            max_workers: Max parallel workers for file analysis
            security_patterns: Custom security patterns (uses defaults if None)
        """
        super().__init__(enable_checkpointing=enable_checkpointing)
        self.max_workers = max_workers
        self.security_patterns = security_patterns or SECURITY_PATTERNS
        self._logger = logging.getLogger("agent.parser")
    
    @property
    def name(self) -> str:
        return "parser"
    
    def _validate_input(self, input_data: ParserInput) -> None:
        """Validate parser input."""
        if not input_data.changed_files:
            raise ValueError("No changed files provided")
        
        if not input_data.repo_path:
            raise ValueError("Repository path is required")
        
        if not os.path.isdir(input_data.repo_path):
            raise ValueError(f"Repository path does not exist: {input_data.repo_path}")
    
    def _execute(self, input_data: ParserInput) -> ParserOutput:
        """Execute parsing on all changed files."""
        output = ParserOutput()
        
        # Filter to supported files
        supported_files = [
            f for f in input_data.changed_files
            if self._is_supported_file(f.path) and not f.is_deleted
        ]
        
        self._logger.info(f"Analyzing {len(supported_files)} supported files")
        
        # Analyze files (parallel or sequential)
        if self.max_workers > 1 and len(supported_files) > 1:
            analyses = self._analyze_files_parallel(
                supported_files,
                input_data.repo_path,
                input_data.complexity_threshold,
                input_data.enable_security_scan,
                input_data.enable_dead_code_detection
            )
        else:
            analyses = [
                self._analyze_file(
                    f,
                    input_data.repo_path,
                    input_data.complexity_threshold,
                    input_data.enable_security_scan,
                    input_data.enable_dead_code_detection
                )
                for f in supported_files
            ]
        
        # Collect results
        for analysis in analyses:
            if analysis.parse_error:
                output.failed_files.append(analysis.file_path)
            else:
                output.files.append(analysis)
        
        # Aggregate statistics
        self._aggregate_stats(output)
        
        return output
    
    def _is_supported_file(self, file_path: str) -> bool:
        """Check if file type is supported for analysis."""
        ext = Path(file_path).suffix.lower()
        return ext in EXTENSION_MAP
    
    def _analyze_files_parallel(
        self,
        files: List[FileChange],
        repo_path: str,
        complexity_threshold: int,
        enable_security: bool,
        enable_dead_code: bool
    ) -> List[FileAnalysis]:
        """Analyze files in parallel."""
        analyses = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._analyze_file,
                    f,
                    repo_path,
                    complexity_threshold,
                    enable_security,
                    enable_dead_code
                ): f.path
                for f in files
            }
            
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    analysis = future.result()
                    analyses.append(analysis)
                except Exception as e:
                    self._logger.error(f"Error analyzing {file_path}: {e}")
                    analyses.append(FileAnalysis(
                        file_path=file_path,
                        language="unknown",
                        total_lines=0,
                        code_lines=0,
                        parse_error=str(e)
                    ))
        
        return analyses
    
    def _analyze_file(
        self,
        file_change: FileChange,
        repo_path: str,
        complexity_threshold: int,
        enable_security: bool,
        enable_dead_code: bool
    ) -> FileAnalysis:
        """Analyze a single file."""
        file_path = file_change.path
        full_path = os.path.join(repo_path, file_path)
        
        # Initialize analysis
        analysis = FileAnalysis(
            file_path=file_path,
            language="unknown",
            total_lines=0,
            code_lines=0
        )
        
        try:
            # Read file content
            if not os.path.exists(full_path):
                analysis.parse_error = f"File not found: {full_path}"
                return analysis
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.splitlines()
            analysis.total_lines = len(lines)
            analysis.code_lines = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
            
            # Detect language
            ext = Path(file_path).suffix.lower()
            language = EXTENSION_MAP.get(ext, "unknown")
            analysis.language = language
            
            if language == "unknown":
                analysis.parse_error = f"Unsupported file type: {ext}"
                return analysis
            
            # Run AST + Semantic pipeline
            pipeline = AnalysisPipeline(language)
            results = pipeline.run_full_pipeline(content)
            
            # Extract functions from AST report
            if results.get("ast_report"):
                ast_report = results["ast_report"]
                analysis.functions = self._extract_functions(ast_report, complexity_threshold)
                analysis.imports = self._extract_imports(ast_report)
                
                # Calculate complexity metrics
                if analysis.functions:
                    complexities = [f.complexity for f in analysis.functions]
                    analysis.avg_complexity = sum(complexities) / len(complexities)
                    analysis.max_complexity = max(complexities)
                    
                    # Check for high complexity
                    for func in analysis.functions:
                        if func.complexity > complexity_threshold:
                            analysis.complexity_issues.append(ComplexityIssue(
                                function_name=func.name,
                                line=func.start_line,
                                complexity=func.complexity,
                                threshold=complexity_threshold
                            ))
            
            # Extract classes and more from semantic report
            if results.get("semantic_report"):
                sem_report = results["semantic_report"]
                analysis.classes = self._extract_classes(sem_report)
                analysis.call_graph = self._extract_call_graph(sem_report)
                analysis.inheritance_graph = self._extract_inheritance(sem_report)
            
            # Security scanning
            if enable_security:
                analysis.security_issues = self._scan_security(content, language, lines)
            
            # Dead code detection
            if enable_dead_code and results.get("ast_report"):
                ast_report = results["ast_report"]
                analysis.dead_code = self._detect_dead_code(ast_report)
            
        except Exception as e:
            self._logger.error(f"Error parsing {file_path}: {e}")
            analysis.parse_error = str(e)
        
        return analysis
    
    def _extract_functions(
        self,
        ast_report: Dict[str, Any],
        complexity_threshold: int
    ) -> List[FunctionInfo]:
        """Extract function information from AST report."""
        functions = []
        
        for func in ast_report.get("functions", []):
            functions.append(FunctionInfo(
                name=func.get("name", "<anonymous>"),
                start_line=func.get("start_line", 0),
                end_line=func.get("end_line", 0),
                complexity=func.get("complexity", 1),
                parameters=func.get("parameters", []),
                has_docstring=False,  # TODO: detect docstrings
            ))
        
        return functions
    
    def _extract_imports(self, ast_report: Dict[str, Any]) -> List[ImportInfo]:
        """Extract import information from AST report."""
        imports = []
        
        for imp in ast_report.get("imports_exports", []):
            if imp.get("kind") == "import":
                statement = imp.get("statement", "")
                imports.append(ImportInfo(
                    module=statement,
                    line=imp.get("start_line", 0),
                    is_used=True  # Will be updated by dead code detection
                ))
        
        return imports
    
    def _extract_classes(self, sem_report: Dict[str, Any]) -> List[ClassInfo]:
        """Extract class information from semantic report."""
        classes = []
        
        for cls in sem_report.get("classes", []):
            inherits = []
            # Find inheritance from hierarchy
            for hier in sem_report.get("inheritance_hierarchy", []):
                if hier.get("class") == cls.get("name"):
                    inherits = hier.get("inherits_from", [])
                    break
            
            classes.append(ClassInfo(
                name=cls.get("name", ""),
                start_line=cls.get("start_line", 0),
                end_line=cls.get("end_line", 0),
                inherits_from=inherits,
            ))
        
        return classes
    
    def _extract_call_graph(self, sem_report: Dict[str, Any]) -> Dict[str, List[str]]:
        """Extract call graph from semantic report."""
        call_graph = {}
        
        for entry in sem_report.get("call_graph", []):
            caller = entry.get("caller", "")
            calls = entry.get("calls", [])
            if caller:
                call_graph[caller] = calls
        
        return call_graph
    
    def _extract_inheritance(self, sem_report: Dict[str, Any]) -> Dict[str, List[str]]:
        """Extract inheritance hierarchy from semantic report."""
        inheritance = {}
        
        for entry in sem_report.get("inheritance_hierarchy", []):
            child = entry.get("class", "")
            parents = entry.get("inherits_from", [])
            if child:
                inheritance[child] = parents
        
        return inheritance
    
    def _scan_security(
        self,
        content: str,
        language: str,
        lines: List[str]
    ) -> List[SecurityIssue]:
        """Scan content for security vulnerabilities."""
        issues = []
        
        for pattern in self.security_patterns:
            # Check if pattern applies to this language
            if language not in pattern.languages:
                continue
            
            try:
                regex = re.compile(pattern.pattern, re.IGNORECASE | re.MULTILINE)
                
                for match in regex.finditer(content):
                    # Find line number
                    line_num = content[:match.start()].count('\n') + 1
                    
                    # Get code snippet
                    snippet = lines[line_num - 1] if line_num <= len(lines) else ""
                    
                    issues.append(SecurityIssue(
                        type=pattern.type,
                        severity=pattern.severity,
                        line=line_num,
                        description=pattern.description,
                        recommendation=pattern.recommendation,
                        code_snippet=snippet.strip(),
                        cwe_id=pattern.cwe_id
                    ))
            except re.error as e:
                self._logger.warning(f"Invalid regex pattern: {pattern.pattern}: {e}")
        
        # Deduplicate issues on same line with same type
        seen = set()
        unique_issues = []
        for issue in issues:
            key = (issue.type, issue.line)
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)
        
        return unique_issues
    
    def _detect_dead_code(self, ast_report: Dict[str, Any]) -> List[DeadCodeInfo]:
        """Detect unused code from AST report."""
        dead_code = []
        
        # Analyze variables
        for var in ast_report.get("variables", []):
            declarations = var.get("declarations", [])
            usages = var.get("usages", [])
            name = var.get("name", "")
            
            # Skip common patterns that are intentionally unused
            if name.startswith("_") or name in ("self", "cls", "args", "kwargs"):
                continue
            
            # Variable declared but never used
            if declarations and not usages:
                dead_code.append(DeadCodeInfo(
                    type=DeadCodeType.UNUSED_VARIABLE,
                    name=name,
                    line=declarations[0],
                ))
        
        # Analyze functions - check if they're called anywhere
        # This is a simplified check - proper analysis would need cross-file analysis
        functions = ast_report.get("functions", [])
        variables = ast_report.get("variables", [])
        
        # Build set of all function names that are referenced
        referenced_functions: Set[str] = set()
        for var in variables:
            usages = var.get("usages", [])
            if usages:
                referenced_functions.add(var.get("name", ""))
        
        for func in functions:
            name = func.get("name", "")
            
            # Skip special methods and main entry points
            if name.startswith("_") or name in ("main", "setup", "teardown"):
                continue
            
            # Skip if function name is used somewhere (could be a reference)
            if name in referenced_functions:
                continue
            
            # This is a heuristic - function defined but name not referenced
            # Note: This has false positives for exported functions, callbacks, etc.
            # In a real implementation, we'd need more sophisticated analysis
        
        return dead_code
    
    def _aggregate_stats(self, output: ParserOutput) -> None:
        """Aggregate statistics across all analyzed files."""
        output.total_files = len(output.files)
        
        total_functions = 0
        total_classes = 0
        total_security = 0
        total_dead = 0
        total_complexity = 0
        files_with_issues = 0
        complexity_sum = 0.0
        
        for f in output.files:
            total_functions += len(f.functions)
            total_classes += len(f.classes)
            total_security += len(f.security_issues)
            total_dead += len(f.dead_code)
            total_complexity += len(f.complexity_issues)
            complexity_sum += f.avg_complexity
            
            if f.security_issues or f.dead_code or f.complexity_issues:
                files_with_issues += 1
        
        output.total_functions = total_functions
        output.total_classes = total_classes
        output.total_security_issues = total_security
        output.total_dead_code = total_dead
        output.total_complexity_issues = total_complexity
        output.files_with_issues = files_with_issues
        
        if output.files:
            output.avg_complexity = complexity_sum / len(output.files)
