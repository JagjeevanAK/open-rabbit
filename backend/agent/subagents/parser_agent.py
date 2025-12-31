"""
Parser Agent

Sub-agent responsible for code understanding and structure extraction.
Uses the Parsers/ module for AST and Semantic analysis.

Responsibilities:
- Parse source files using tree-sitter AST
- Build semantic graphs (imports, calls, inheritance)
- Extract symbols (functions, classes, methods)
- Identify hotspots (high complexity areas)
- Support both local filesystem and sandbox environments

Constraints:
- Does NOT do code review
- Does NOT suggest changes
- Only parses and summarizes
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor

from .base_agent import BaseAgent, AgentConfig
from ..schemas.common import FileInfo
from ..schemas.parser_output import (
    ParserOutput,
    FileMetadata,
    Symbol,
    SymbolType,
    CallGraphEntry,
    Hotspot,
)
from ..logging_config import (
    get_logger,
    get_session_id,
    log_with_data,
)

if TYPE_CHECKING:
    from ..services.sandbox_manager import SandboxManager

logger = get_logger(__name__)

# Add Parsers directory to path for imports
PARSERS_DIR = Path(__file__).parent.parent.parent.parent / "Parsers"
if str(PARSERS_DIR) not in sys.path:
    sys.path.insert(0, str(PARSERS_DIR))


# Complexity thresholds for hotspot detection
COMPLEXITY_WARNING_THRESHOLD = 10
COMPLEXITY_CRITICAL_THRESHOLD = 15
LARGE_FUNCTION_LINES = 50
MANY_PARAMS_THRESHOLD = 5


class ParserAgent(BaseAgent[ParserOutput]):
    """
    Parser Agent for code understanding and structure extraction.
    
    This agent uses the existing Parsers/ infrastructure to:
    1. Parse source code into AST using tree-sitter
    2. Build semantic graphs with relationships
    3. Generate AST and Semantic reports
    4. Extract symbols and identify hotspots
    
    Supports both local filesystem and E2B sandbox environments.
    
    NO LLM calls are made - this is pure static analysis.
    """
    
    def __init__(
        self, 
        config: Optional[AgentConfig] = None,
        sandbox_manager: Optional["SandboxManager"] = None,
        session_id: Optional[str] = None,
    ):
        """
        Initialize the Parser Agent.
        
        Args:
            config: Agent configuration
            sandbox_manager: Optional SandboxManager for reading files from E2B sandbox
            session_id: Session ID for sandbox operations
        """
        if config is None:
            config = AgentConfig(
                name="parser_agent",
                timeout_seconds=120.0,  # 2 minutes for parsing
                max_retries=2,
            )
        super().__init__(config)
        self._pipeline = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._sandbox_manager = sandbox_manager
        self._session_id = session_id
    
    @property
    def name(self) -> str:
        return "parser_agent"
    
    def _get_pipeline(self):
        """Lazy load the analysis pipeline from Parsers/."""
        if self._pipeline is None:
            try:
                from pipeline import AnalysisPipeline
                self._pipeline = AnalysisPipeline()
            except ImportError as e:
                logger.error(f"Failed to import AnalysisPipeline: {e}")
                raise ImportError(
                    "AnalysisPipeline not found. Ensure Parsers/ directory is in the path."
                ) from e
        return self._pipeline
    
    async def _execute(self, files: List[FileInfo]) -> ParserOutput:
        """
        Execute parsing on the provided files.
        
        Args:
            files: List of FileInfo objects to parse.
            
        Returns:
            ParserOutput with parsed metadata.
        """
        output = ParserOutput()
        session_id = get_session_id() or "unknown"
        start_time = time.perf_counter()
        
        # Determine mode
        mode = "sandbox" if (self._sandbox_manager and self._session_id) else "local"
        
        log_with_data(logger, 20, "Starting code parsing", {
            "session_id": session_id,
            "total_files": len(files),
            "languages": list(set(self._detect_language(f.path) for f in files)),
            "mode": mode,
        })
        
        # Pre-fetch file contents if using sandbox
        if mode == "sandbox":
            files = await self._prefetch_file_contents(files)
        
        # Process files concurrently
        tasks = [self._parse_file(file_info) for file_info in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        files_parsed = 0
        files_failed = 0
        
        for file_info, result in zip(files, results):
            if isinstance(result, Exception):
                files_failed += 1
                output.errors.append({
                    "file": file_info.path,
                    "error": str(result),
                })
                log_with_data(logger, 30, f"Failed to parse file: {file_info.path}", {
                    "session_id": session_id,
                    "file": file_info.path,
                    "error": str(result),
                    "error_type": type(result).__name__,
                })
            else:
                files_parsed += 1
                file_meta, symbols, call_entries, hotspots, ast_report, semantic_report = result
                
                if file_meta:
                    output.files.append(file_meta)
                output.symbols.extend(symbols)
                output.call_graph.extend(call_entries)
                output.hotspots.extend(hotspots)
                
                if ast_report:
                    output.ast_reports[file_info.path] = ast_report
                if semantic_report:
                    output.semantic_reports[file_info.path] = semantic_report
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        log_with_data(logger, 20, "Code parsing completed", {
            "session_id": session_id,
            "files_parsed": files_parsed,
            "files_failed": files_failed,
            "symbols_extracted": len(output.symbols),
            "hotspots_found": len(output.hotspots),
            "duration_ms": round(duration_ms, 2),
            "mode": mode,
        })
        
        return output
    
    async def _prefetch_file_contents(self, files: List[FileInfo]) -> List[FileInfo]:
        """
        Pre-fetch file contents from sandbox.
        
        This populates the content field of FileInfo objects that don't have it,
        reading from the sandbox in parallel.
        
        Args:
            files: List of FileInfo objects
            
        Returns:
            Updated list of FileInfo objects with content populated
        """
        if not self._sandbox_manager or not self._session_id:
            return files
        
        updated_files = []
        
        for file_info in files:
            if file_info.content:
                updated_files.append(file_info)
                continue
            
            try:
                content = await self._sandbox_manager.read_file(
                    self._session_id,
                    file_info.path
                )
                # Create new FileInfo with content
                updated_files.append(FileInfo(
                    path=file_info.path,
                    content=content,
                    language=file_info.language,
                    diff=file_info.diff,
                    is_new=file_info.is_new,
                    is_deleted=file_info.is_deleted,
                    is_modified=file_info.is_modified,
                    start_line=file_info.start_line,
                    end_line=file_info.end_line,
                ))
            except Exception as e:
                logger.warning(f"Failed to prefetch {file_info.path}: {e}")
                updated_files.append(file_info)
        
        return updated_files
    
    async def _parse_file(self, file_info: FileInfo) -> tuple:
        """
        Parse a single file asynchronously.
        
        Runs the CPU-intensive parsing in a thread pool.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._parse_file_sync,
            file_info
        )
    
    def _parse_file_sync(self, file_info: FileInfo) -> tuple:
        """
        Synchronously parse a single file.
        
        Returns:
            Tuple of (FileMetadata, symbols, call_entries, hotspots, ast_report, semantic_report)
        """
        try:
            # Import report generators
            from analysis_reports import generate_ast_report, generate_semantic_report
            
            pipeline = self._get_pipeline()
            
            # Determine language from file extension
            language = self._detect_language(file_info.path)
            if not language:
                raise ValueError(f"Unsupported file type: {file_info.path}")
            
            # Get source code
            source_code = self._get_source_code(file_info)
            if source_code is None:
                raise ValueError(f"No source code available for: {file_info.path}")
            
            source_bytes = source_code.encode('utf-8') if isinstance(source_code, str) else source_code
            
            # Parse AST
            ast_tree = pipeline.parse_code(source_code, language)
            if ast_tree is None:
                raise ValueError(f"Failed to parse AST for: {file_info.path}")
            
            # Build semantic graph
            semantic_graph = pipeline.build_semantic()
            
            # Generate reports
            ast_report = generate_ast_report(ast_tree, source_bytes, language)
            semantic_report = generate_semantic_report(semantic_graph) if semantic_graph else {}
            
            # Extract metadata
            file_meta = self._build_file_metadata(file_info, ast_report, semantic_report, language)
            
            # Extract symbols
            symbols = self._extract_symbols(file_info.path, ast_report, semantic_report)
            
            # Build call graph entries
            call_entries = self._extract_call_graph(file_info.path, semantic_report)
            
            # Find hotspots
            hotspots = self._find_hotspots(file_info.path, ast_report, semantic_report)
            
            return (file_meta, symbols, call_entries, hotspots, ast_report, semantic_report)
            
        except Exception as e:
            log_with_data(logger, 40, f"Error parsing file: {file_info.path}", {
                "file": file_info.path,
                "error": str(e),
                "error_type": type(e).__name__,
            })
            raise
    
    def _detect_language(self, file_path: str) -> Optional[str]:
        """Detect language from file extension."""
        ext = Path(file_path).suffix.lower()
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
        }
        return language_map.get(ext)
    
    def _get_source_code(self, file_info: FileInfo) -> Optional[str]:
        """Get source code from FileInfo."""
        if file_info.content:
            return file_info.content
        
        # Try to read from disk if path exists (local mode)
        if os.path.exists(file_info.path):
            with open(file_info.path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        
        return None
    
    async def _get_source_code_async(self, file_info: FileInfo) -> Optional[str]:
        """
        Get source code from FileInfo, with sandbox support.
        
        Args:
            file_info: FileInfo object
            
        Returns:
            Source code as string, or None if unavailable
        """
        # First check if content is already provided
        if file_info.content:
            return file_info.content
        
        # Try sandbox if available
        if self._sandbox_manager and self._session_id:
            try:
                content = await self._sandbox_manager.read_file(
                    self._session_id, 
                    file_info.path
                )
                return content
            except Exception as e:
                logger.warning(
                    f"Failed to read from sandbox: {file_info.path}: {e}"
                )
                # Fall through to local filesystem
        
        # Try local filesystem
        if os.path.exists(file_info.path):
            with open(file_info.path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        
        return None
    
    def _build_file_metadata(
        self,
        file_info: FileInfo,
        ast_report: Dict[str, Any],
        semantic_report: Dict[str, Any],
        language: str
    ) -> FileMetadata:
        """Build FileMetadata from reports."""
        ast_summary = ast_report.get("summary", {})
        semantic_summary = semantic_report.get("summary", {})
        
        # Calculate average complexity
        functions = ast_report.get("functions", [])
        if functions:
            complexities = [f.get("complexity", 1) for f in functions]
            avg_complexity = sum(complexities) / len(complexities)
        else:
            avg_complexity = 0.0
        
        # Count lines from content
        line_count = 0
        if file_info.content:
            line_count = file_info.content.count('\n') + 1
        elif os.path.exists(file_info.path):
            with open(file_info.path, 'r', encoding='utf-8', errors='replace') as f:
                line_count = sum(1 for _ in f)
        
        # Detect if file has tests
        has_tests = self._detect_tests(file_info.path, ast_report)
        
        return FileMetadata(
            path=file_info.path,
            language=language,
            line_count=line_count,
            function_count=ast_summary.get("function_count", 0),
            class_count=semantic_summary.get("class_count", 0),
            import_count=ast_summary.get("import_statement_count", 0),
            export_count=ast_summary.get("export_statement_count", 0),
            complexity_score=round(avg_complexity, 2),
            has_tests=has_tests,
            summary={
                "ast": ast_summary,
                "semantic": semantic_summary,
            },
        )
    
    def _detect_tests(self, file_path: str, ast_report: Dict[str, Any]) -> bool:
        """Detect if a file contains test code."""
        file_name = Path(file_path).name.lower()
        
        # Check file name patterns
        test_patterns = ["test_", "_test", ".test.", ".spec.", "tests/", "test/"]
        if any(pattern in file_name for pattern in test_patterns):
            return True
        
        # Check function names
        functions = ast_report.get("functions", [])
        for func in functions:
            name = func.get("name", "").lower()
            if name.startswith("test") or name.startswith("it_") or name == "describe":
                return True
        
        return False
    
    def _extract_symbols(
        self,
        file_path: str,
        ast_report: Dict[str, Any],
        semantic_report: Dict[str, Any]
    ) -> List[Symbol]:
        """Extract Symbol objects from reports."""
        symbols = []
        
        # Extract functions from AST report
        for func in ast_report.get("functions", []):
            symbols.append(Symbol(
                name=func.get("name", "<anonymous>"),
                symbol_type=SymbolType.FUNCTION,
                file_path=file_path,
                start_line=func.get("start_line", 0),
                end_line=func.get("end_line"),
                parameters=func.get("parameters", []),
                complexity=func.get("complexity"),
            ))
        
        # Extract classes from semantic report
        for cls in semantic_report.get("classes", []):
            symbols.append(Symbol(
                name=cls.get("name", "<anonymous>"),
                symbol_type=SymbolType.CLASS,
                file_path=file_path,
                start_line=cls.get("start_line", 0),
                end_line=cls.get("end_line"),
                scope=cls.get("scope"),
            ))
        
        # Extract imports
        for imp in ast_report.get("imports_exports", []):
            if imp.get("kind") == "import":
                symbols.append(Symbol(
                    name=imp.get("statement", "")[:50],  # Truncate long imports
                    symbol_type=SymbolType.IMPORT,
                    file_path=file_path,
                    start_line=imp.get("start_line", 0),
                    end_line=imp.get("end_line"),
                ))
        
        # Extract exports
        for exp in ast_report.get("imports_exports", []):
            if exp.get("kind") == "export":
                symbols.append(Symbol(
                    name=exp.get("statement", "")[:50],
                    symbol_type=SymbolType.EXPORT,
                    file_path=file_path,
                    start_line=exp.get("start_line", 0),
                    end_line=exp.get("end_line"),
                ))
        
        return symbols
    
    def _extract_call_graph(
        self,
        file_path: str,
        semantic_report: Dict[str, Any]
    ) -> List[CallGraphEntry]:
        """Extract call graph entries from semantic report."""
        entries = []
        
        for call in semantic_report.get("call_graph", []):
            entries.append(CallGraphEntry(
                caller=f"{file_path}:{call.get('caller', '')}",
                caller_file=file_path,
                caller_line=0,  # Not always available
                callees=call.get("calls", []),
            ))
        
        return entries
    
    def _find_hotspots(
        self,
        file_path: str,
        ast_report: Dict[str, Any],
        semantic_report: Dict[str, Any]
    ) -> List[Hotspot]:
        """Find code hotspots based on complexity metrics."""
        hotspots = []
        
        # Check function complexity
        for func in ast_report.get("functions", []):
            complexity = func.get("complexity", 0)
            
            if complexity > COMPLEXITY_CRITICAL_THRESHOLD:
                hotspots.append(Hotspot(
                    file_path=file_path,
                    symbol_name=func.get("name", "<anonymous>"),
                    start_line=func.get("start_line", 0),
                    end_line=func.get("end_line"),
                    hotspot_type="high_complexity",
                    severity="critical",
                    metric_value=complexity,
                    threshold=COMPLEXITY_CRITICAL_THRESHOLD,
                    message=f"Function has critical complexity ({complexity}). Consider refactoring.",
                ))
            elif complexity > COMPLEXITY_WARNING_THRESHOLD:
                hotspots.append(Hotspot(
                    file_path=file_path,
                    symbol_name=func.get("name", "<anonymous>"),
                    start_line=func.get("start_line", 0),
                    end_line=func.get("end_line"),
                    hotspot_type="high_complexity",
                    severity="warning",
                    metric_value=complexity,
                    threshold=COMPLEXITY_WARNING_THRESHOLD,
                    message=f"Function has high complexity ({complexity}). May be hard to maintain.",
                ))
            
            # Check parameter count
            params = func.get("parameters", [])
            if len(params) > MANY_PARAMS_THRESHOLD:
                hotspots.append(Hotspot(
                    file_path=file_path,
                    symbol_name=func.get("name", "<anonymous>"),
                    start_line=func.get("start_line", 0),
                    end_line=func.get("end_line"),
                    hotspot_type="many_params",
                    severity="warning",
                    metric_value=len(params),
                    threshold=MANY_PARAMS_THRESHOLD,
                    message=f"Function has {len(params)} parameters. Consider using an options object.",
                ))
            
            # Check function length
            start = func.get("start_line", 0)
            end = func.get("end_line", 0)
            if start and end:
                length = end - start
                if length > LARGE_FUNCTION_LINES:
                    hotspots.append(Hotspot(
                        file_path=file_path,
                        symbol_name=func.get("name", "<anonymous>"),
                        start_line=start,
                        end_line=end,
                        hotspot_type="large_function",
                        severity="warning",
                        metric_value=length,
                        threshold=LARGE_FUNCTION_LINES,
                        message=f"Function is {length} lines long. Consider breaking it up.",
                    ))
        
        return hotspots
    
    def __del__(self):
        """Cleanup executor on deletion."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
