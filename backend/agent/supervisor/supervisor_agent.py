"""
Supervisor Agent

Main orchestrator for the multi-agent code review system.
Implements a LangGraph state machine with:
- Checkpointing for restart capability (database + memory)
- Async agent execution
- Knowledge Base integration
- E2B Sandbox management for isolated code analysis
- Comprehensive production logging

The Supervisor:
- Owns global context
- Has exclusive access to Knowledge Base
- Manages E2B sandbox lifecycle
- Decides which sub-agents to invoke
- Aggregates results into single structured output
"""

import asyncio
import json
import os
import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Annotated, TypedDict, Sequence, Callable

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage

from ..schemas.common import (
    ReviewRequest,
    SupervisorOutput,
    UserIntent,
    IntentType,
    KBContext,
    FileInfo,
    AgentStatus,
    CheckpointData,
    AgentResult,
)
from ..schemas.parser_output import ParserOutput
from ..schemas.review_output import ReviewOutput
from ..schemas.test_output import TestOutput
from ..subagents.parser_agent import ParserAgent
from ..subagents.review_agent import CodeReviewAgent, MockCodeReviewAgent
from ..subagents.unit_test_agent import UnitTestAgent, MockUnitTestAgent
from ..llm_factory import LLMFactory, LLMProvider
from ..services.kb_client import KBClient, KBClientConfig
from ..services.sandbox_manager import (
    SandboxManager, 
    SandboxConfig, 
    create_sandbox_manager,
    SandboxError,
    SandboxCreationError,
)
from .intent_parser import IntentParser
from .result_aggregator import ResultAggregator

# Import production logging
from ..logging_config import (
    get_logger,
    set_session_id,
    get_session_id,
    log_with_data,
    timed,
    AsyncLogContext,
    log_workflow_transition,
    log_agent_start,
    log_agent_complete,
    log_checkpoint_saved,
    log_checkpoint_restored,
    setup_logging,
)

# Initialize logging
setup_logging()
logger = get_logger(__name__)


@dataclass
class SupervisorConfig:
    """Configuration for the Supervisor Agent."""
    # LLM settings
    llm_provider: LLMProvider = LLMProvider.OPENAI
    llm_model: Optional[str] = None
    
    # Knowledge Base settings
    kb_url: Optional[str] = None
    kb_enabled: bool = True
    kb_elasticsearch_url: Optional[str] = None
    
    # E2B Sandbox settings
    sandbox_enabled: bool = True  # Use E2B sandbox for isolation
    sandbox_timeout_ms: int = 300_000  # 5 minutes
    sandbox_template_id: Optional[str] = None  # Custom template or use default
    
    # Execution settings
    timeout_seconds: float = 600.0  # 10 minutes total
    max_retries: int = 3
    
    # Checkpointing - uses database for persistence
    enable_checkpointing: bool = True
    
    # Mock mode for testing
    use_mock_agents: bool = False


# LangGraph State Definition
class SupervisorState(TypedDict, total=False):
    """State for the LangGraph supervisor workflow."""
    # Input
    request: Dict[str, Any]  # Serialized ReviewRequest
    session_id: str
    
    # Parsed intent
    intent: Dict[str, Any]  # Serialized UserIntent
    
    # Knowledge Base context
    kb_context: Dict[str, Any]  # Serialized KBContext
    
    # Sandbox state
    sandbox_repo_path: str  # Path to cloned repo inside sandbox
    sandbox_active: bool    # Whether sandbox is active
    
    # Agent outputs
    parser_output: Dict[str, Any]
    review_output: Dict[str, Any]
    test_output: Dict[str, Any]
    
    # Agent results with status
    parser_result: Dict[str, Any]
    review_result: Dict[str, Any]
    test_result: Dict[str, Any]
    
    # Workflow control
    current_step: str
    completed_steps: List[str]
    errors: List[str]
    
    # Final output
    final_output: Dict[str, Any]
    
    # Timing
    started_at: str
    completed_at: str


class SupervisorAgent:
    """
    Main Supervisor Agent using LangGraph for orchestration.
    
    Features:
    - Async execution of sub-agents
    - Checkpointing for restart capability
    - Knowledge Base integration
    - E2B Sandbox management for isolated code analysis
    - Graceful error handling
    """
    
    def __init__(self, config: Optional[SupervisorConfig] = None):
        """
        Initialize the Supervisor Agent.
        
        Args:
            config: Supervisor configuration
        """
        self.config = config or SupervisorConfig()
        
        # Initialize components
        self.intent_parser = IntentParser()
        self.aggregator = ResultAggregator()
        
        # Initialize KB client
        kb_config = KBClientConfig(
            base_url=self.config.kb_url or os.getenv("KB_SERVICE_URL", "http://localhost:8000"),
            elasticsearch_url=self.config.kb_elasticsearch_url or os.getenv("ELASTICSEARCH_URL"),
        )
        self._kb_client = KBClient(kb_config)
        
        # Initialize sandbox manager (if enabled)
        self._sandbox_manager: Optional[SandboxManager] = None
        if self.config.sandbox_enabled:
            try:
                sandbox_config = SandboxConfig(
                    api_key=os.getenv("E2B_API_KEY"),
                    timeout_ms=self.config.sandbox_timeout_ms,
                    template_id=self.config.sandbox_template_id or os.getenv("E2B_TEMPLATE_ID"),
                    max_retries=self.config.max_retries,
                )
                self._sandbox_manager = SandboxManager(sandbox_config)
                logger.info("SandboxManager initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize SandboxManager: {e}. Running without sandbox.")
                self._sandbox_manager = None
        
        # Initialize sub-agents (lazy loaded)
        self._parser_agent: Optional[ParserAgent] = None
        self._review_agent: Optional[CodeReviewAgent] = None
        self._test_agent: Optional[UnitTestAgent] = None
        
        # Checkpointing
        self._checkpointer = MemorySaver() if self.config.enable_checkpointing else None
        
        # Build the workflow graph
        self._graph = self._build_graph()
        self._compiled_graph = None
    
    @property
    def parser_agent(self) -> ParserAgent:
        """Lazy-load parser agent."""
        if self._parser_agent is None:
            # Note: sandbox_manager and session_id are set per-run via run_with_sandbox
            self._parser_agent = ParserAgent()
        return self._parser_agent
    
    def _get_parser_agent_for_session(self, session_id: str) -> ParserAgent:
        """
        Get parser agent configured for the current session.
        
        This creates a new ParserAgent with sandbox_manager and session_id set.
        """
        return ParserAgent(
            sandbox_manager=self._sandbox_manager,
            session_id=session_id,
        )
    
    @property
    def review_agent(self) -> CodeReviewAgent:
        """Lazy-load review agent."""
        if self._review_agent is None:
            if self.config.use_mock_agents:
                self._review_agent = MockCodeReviewAgent()
            else:
                self._review_agent = CodeReviewAgent(
                    provider=self.config.llm_provider,
                    model=self.config.llm_model,
                )
        return self._review_agent
    
    @property
    def test_agent(self) -> UnitTestAgent:
        """Lazy-load test agent."""
        if self._test_agent is None:
            if self.config.use_mock_agents:
                self._test_agent = MockUnitTestAgent()
            else:
                self._test_agent = UnitTestAgent(
                    provider=self.config.llm_provider,
                    model=self.config.llm_model,
                )
        return self._test_agent
    
    @property
    def compiled_graph(self):
        """Get or compile the graph."""
        if self._compiled_graph is None:
            self._compiled_graph = self._graph.compile(
                checkpointer=self._checkpointer
            )
        return self._compiled_graph
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        graph = StateGraph(SupervisorState)
        
        # Add nodes for each step
        graph.add_node("parse_intent", self._node_parse_intent)
        graph.add_node("setup_sandbox", self._node_setup_sandbox)
        graph.add_node("fetch_kb", self._node_fetch_kb)
        graph.add_node("run_parser", self._node_run_parser)
        graph.add_node("run_review", self._node_run_review)
        graph.add_node("run_tests", self._node_run_tests)
        graph.add_node("aggregate", self._node_aggregate)
        graph.add_node("cleanup_sandbox", self._node_cleanup_sandbox)
        
        # Define edges
        graph.set_entry_point("parse_intent")
        graph.add_edge("parse_intent", "setup_sandbox")
        graph.add_edge("setup_sandbox", "fetch_kb")
        graph.add_edge("fetch_kb", "run_parser")
        
        # Conditional edge from parser to review or tests
        graph.add_conditional_edges(
            "run_parser",
            self._route_after_parser,
            {
                "review": "run_review",
                "tests": "run_tests",
                "aggregate": "aggregate",
            }
        )
        
        # Conditional edge from review
        graph.add_conditional_edges(
            "run_review",
            self._route_after_review,
            {
                "tests": "run_tests",
                "aggregate": "aggregate",
            }
        )
        
        # Tests always go to aggregate
        graph.add_edge("run_tests", "aggregate")
        
        # Aggregate goes to cleanup
        graph.add_edge("aggregate", "cleanup_sandbox")
        
        # Cleanup ends the workflow
        graph.add_edge("cleanup_sandbox", END)
        
        return graph
    
    def _route_after_parser(self, state: SupervisorState) -> str:
        """Route after parser completes."""
        intent = state.get("intent", {})
        
        if intent.get("should_review", True):
            log_workflow_transition(logger, "run_parser", "run_review", "Intent requires code review")
            return "review"
        elif intent.get("should_generate_tests", False):
            log_workflow_transition(logger, "run_parser", "run_tests", "Intent requires test generation only")
            return "tests"
        else:
            log_workflow_transition(logger, "run_parser", "aggregate", "No further processing needed")
            return "aggregate"
    
    def _route_after_review(self, state: SupervisorState) -> str:
        """Route after review completes."""
        intent = state.get("intent", {})
        
        if intent.get("should_generate_tests", False):
            log_workflow_transition(logger, "run_review", "run_tests", "Intent also requires test generation")
            return "tests"
        else:
            log_workflow_transition(logger, "run_review", "aggregate", "Review complete, aggregating results")
            return "aggregate"
    
    async def _node_parse_intent(self, state: SupervisorState) -> Dict[str, Any]:
        """Parse user intent from request."""
        start_time = time.perf_counter()
        session_id = state.get("session_id", "unknown")
        set_session_id(session_id)
        
        log_with_data(logger, 20, "Parsing user intent", {
            "step": "parse_intent",
            "session_id": session_id,
        })
        
        request_dict = state.get("request", {})
        request = ReviewRequest.from_dict(request_dict)
        
        intent = self.intent_parser.parse(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        log_with_data(logger, 20, "Intent parsed successfully", {
            "step": "parse_intent",
            "should_review": intent.should_review,
            "should_generate_tests": intent.should_generate_tests,
            "test_targets_count": len(intent.test_targets),
            "review_scope": intent.review_scope,
            "duration_ms": round(duration_ms, 2),
        })
        
        log_checkpoint_saved(logger, session_id, "parse_intent")
        
        return {
            "intent": intent.to_dict(),
            "current_step": "intent_parsed",
            "completed_steps": state.get("completed_steps", []) + ["parse_intent"],
        }
    
    async def _node_setup_sandbox(self, state: SupervisorState) -> Dict[str, Any]:
        """
        Setup E2B sandbox and clone repository.
        
        Creates an isolated cloud sandbox environment for code analysis.
        Clones the repository inside the sandbox.
        """
        start_time = time.perf_counter()
        session_id = state.get("session_id", "unknown")
        request_dict = state.get("request", {})
        
        log_with_data(logger, 20, "Setting up E2B sandbox", {
            "step": "setup_sandbox",
            "sandbox_enabled": self.config.sandbox_enabled,
            "session_id": session_id,
        })
        
        sandbox_repo_path = None
        sandbox_active = False
        errors = state.get("errors", [])
        
        if self._sandbox_manager and self.config.sandbox_enabled:
            try:
                # Create sandbox for this session
                await self._sandbox_manager.create_sandbox(
                    session_id=session_id,
                    metadata={"pr_number": str(request_dict.get("pr_number", ""))}
                )
                
                # Clone repository if URL is provided
                repo_url = request_dict.get("repo_url")
                branch = request_dict.get("branch", "main")
                
                if repo_url:
                    sandbox_repo_path = await self._sandbox_manager.clone_repo(
                        session_id=session_id,
                        repo_url=repo_url,
                        branch=branch,
                    )
                    sandbox_active = True
                    
                    log_with_data(logger, 20, "Sandbox setup complete", {
                        "step": "setup_sandbox",
                        "repo_path": sandbox_repo_path,
                        "session_id": session_id,
                    })
                else:
                    # No repo URL - sandbox created but no clone
                    sandbox_active = True
                    log_with_data(logger, 20, "Sandbox created (no repo to clone)", {
                        "step": "setup_sandbox",
                        "session_id": session_id,
                    })
                    
            except SandboxCreationError as e:
                log_with_data(logger, 40, f"Sandbox creation failed: {e}", {
                    "step": "setup_sandbox",
                    "error": str(e),
                })
                errors.append(f"Sandbox creation failed: {str(e)}")
                
            except SandboxError as e:
                log_with_data(logger, 40, f"Sandbox operation failed: {e}", {
                    "step": "setup_sandbox",
                    "error": str(e),
                })
                errors.append(f"Sandbox operation failed: {str(e)}")
                
            except Exception as e:
                log_with_data(logger, 40, f"Unexpected sandbox error: {e}", {
                    "step": "setup_sandbox",
                    "error": str(e),
                    "error_type": type(e).__name__,
                })
                errors.append(f"Sandbox error: {str(e)}")
        else:
            log_with_data(logger, 20, "Sandbox disabled, skipping setup", {
                "step": "setup_sandbox",
            })
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_checkpoint_saved(logger, session_id, "setup_sandbox")
        
        return {
            "sandbox_repo_path": sandbox_repo_path or "",
            "sandbox_active": sandbox_active,
            "current_step": "sandbox_ready",
            "completed_steps": state.get("completed_steps", []) + ["setup_sandbox"],
            "errors": errors,
        }
    
    async def _node_cleanup_sandbox(self, state: SupervisorState) -> Dict[str, Any]:
        """
        Cleanup E2B sandbox after workflow completion.
        
        Kills the sandbox to free resources and prevent charges.
        """
        session_id = state.get("session_id", "unknown")
        sandbox_active = state.get("sandbox_active", False)
        
        log_with_data(logger, 20, "Cleaning up sandbox", {
            "step": "cleanup_sandbox",
            "sandbox_active": sandbox_active,
            "session_id": session_id,
        })
        
        if self._sandbox_manager and sandbox_active:
            try:
                await self._sandbox_manager.kill_sandbox(session_id)
                log_with_data(logger, 20, "Sandbox cleanup complete", {
                    "step": "cleanup_sandbox",
                    "session_id": session_id,
                })
            except Exception as e:
                log_with_data(logger, 30, f"Sandbox cleanup error (non-fatal): {e}", {
                    "step": "cleanup_sandbox",
                    "error": str(e),
                })
        
        return {
            "sandbox_active": False,
            "current_step": "cleanup_complete",
            "completed_steps": state.get("completed_steps", []) + ["cleanup_sandbox"],
        }

    async def _node_fetch_kb(self, state: SupervisorState) -> Dict[str, Any]:
        """Fetch Knowledge Base context."""
        start_time = time.perf_counter()
        session_id = state.get("session_id", "unknown")
        
        log_with_data(logger, 20, "Fetching Knowledge Base context", {
            "step": "fetch_kb",
            "kb_enabled": self.config.kb_enabled,
            "kb_url": self.config.kb_url,
        })
        
        kb_context = KBContext()
        
        if self.config.kb_enabled and self.config.kb_url:
            try:
                request_dict = state.get("request", {})
                kb_context = await self._fetch_kb_context(request_dict)
                
                log_with_data(logger, 20, "KB context fetched successfully", {
                    "step": "fetch_kb",
                    "learnings_count": len(kb_context.learnings),
                    "coding_style_count": len(kb_context.coding_style),
                    "best_practices_count": len(kb_context.best_practices),
                    "conventions_count": len(kb_context.conventions),
                })
            except Exception as e:
                log_with_data(logger, 30, f"Failed to fetch KB context: {e}", {
                    "step": "fetch_kb",
                    "error": str(e),
                })
                state.get("errors", []).append(f"KB fetch failed: {str(e)}")
        else:
            log_with_data(logger, 20, "KB disabled or URL not configured, skipping", {
                "step": "fetch_kb",
            })
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        log_checkpoint_saved(logger, session_id, "fetch_kb")
        
        return {
            "kb_context": kb_context.to_dict(),
            "current_step": "kb_fetched",
            "completed_steps": state.get("completed_steps", []) + ["fetch_kb"],
        }
    
    async def _node_run_parser(self, state: SupervisorState) -> Dict[str, Any]:
        """Run the Parser Agent."""
        start_time = time.perf_counter()
        session_id = state.get("session_id", "unknown")
        sandbox_active = state.get("sandbox_active", False)
        sandbox_repo_path = state.get("sandbox_repo_path", "")
        
        request_dict = state.get("request", {})
        files = [FileInfo.from_dict(f) for f in request_dict.get("files", [])]
        
        # Update file paths to sandbox paths if sandbox is active
        if sandbox_active and sandbox_repo_path:
            files = self._update_file_paths_for_sandbox(files, sandbox_repo_path)
        
        mode = "sandbox" if sandbox_active else "local"
        log_agent_start(logger, "ParserAgent", len(files), 
                       languages=list(set(f.language for f in files if f.language)),
                       mode=mode)
        
        # Use sandbox-enabled parser if sandbox is active
        if sandbox_active and self._sandbox_manager:
            parser = self._get_parser_agent_for_session(session_id)
        else:
            parser = self.parser_agent
        
        result = await parser.run(files)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        output_dict = result.output.to_dict() if result.output else {}
        
        # Log detailed results
        symbols_count = len(output_dict.get("symbols", [])) if output_dict else 0
        hotspots_count = len(output_dict.get("hotspots", [])) if output_dict else 0
        
        log_agent_complete(logger, "ParserAgent", duration_ms, {
            "status": result.status.value,
            "files_parsed": len(files),
            "symbols_found": symbols_count,
            "hotspots_identified": hotspots_count,
            "mode": mode,
        })
        
        log_checkpoint_saved(logger, session_id, "run_parser")
        
        return {
            "parser_output": output_dict,
            "parser_result": result.to_dict(),
            "current_step": "parser_complete",
            "completed_steps": state.get("completed_steps", []) + ["run_parser"],
        }
    
    def _update_file_paths_for_sandbox(
        self, 
        files: List[FileInfo], 
        sandbox_repo_path: str
    ) -> List[FileInfo]:
        """
        Update file paths to point to sandbox locations.
        
        Converts relative paths (e.g., 'src/main.py') to sandbox absolute paths
        (e.g., '/home/user/repos/owner-repo/src/main.py').
        
        Args:
            files: List of FileInfo objects
            sandbox_repo_path: Path to cloned repo inside sandbox
            
        Returns:
            Updated list of FileInfo objects with sandbox paths
        """
        updated_files = []
        
        for file_info in files:
            # If path is already absolute and in sandbox, keep it
            if file_info.path.startswith("/home/user/repos"):
                updated_files.append(file_info)
                continue
            
            # Convert relative path to sandbox path
            rel_path = file_info.path.lstrip("/")
            sandbox_path = f"{sandbox_repo_path}/{rel_path}"
            
            updated_files.append(FileInfo(
                path=sandbox_path,
                content=file_info.content,
                diff=file_info.diff,
                language=file_info.language,
                is_new=file_info.is_new,
                is_deleted=file_info.is_deleted,
                is_modified=file_info.is_modified,
                start_line=file_info.start_line,
                end_line=file_info.end_line,
            ))
        
        return updated_files
    
    async def _node_run_review(self, state: SupervisorState) -> Dict[str, Any]:
        """Run the Code Review Agent."""
        start_time = time.perf_counter()
        session_id = state.get("session_id", "unknown")
        
        request_dict = state.get("request", {})
        files = [FileInfo.from_dict(f) for f in request_dict.get("files", [])]
        
        parser_output = ParserOutput.from_dict(state.get("parser_output", {}))
        kb_context = KBContext.from_dict(state.get("kb_context", {}))
        
        kb_learnings_count = (
            len(kb_context.learnings) + 
            len(kb_context.coding_style) + 
            len(kb_context.best_practices)
        )
        
        log_agent_start(logger, "CodeReviewAgent", len(files),
                       model=self.config.llm_model or "default",
                       kb_learnings=kb_learnings_count)
        
        result = await self.review_agent.run(
            parsed_metadata=parser_output,
            kb_context=kb_context,
            files=files,
        )
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        output_dict = result.output.to_dict() if result.output else {}
        
        # Log detailed results
        issues_count = output_dict.get("total_issues", 0) if output_dict else 0
        critical_count = sum(1 for fs in output_dict.get("file_summaries", []) 
                           for _ in range(fs.get("critical_count", 0))) if output_dict else 0
        
        log_agent_complete(logger, "CodeReviewAgent", duration_ms, {
            "status": result.status.value,
            "files_reviewed": len(files),
            "total_issues": issues_count,
            "critical_issues": critical_count,
        })
        
        log_checkpoint_saved(logger, session_id, "run_review")
        
        return {
            "review_output": output_dict,
            "review_result": result.to_dict(),
            "current_step": "review_complete",
            "completed_steps": state.get("completed_steps", []) + ["run_review"],
        }
    
    async def _node_run_tests(self, state: SupervisorState) -> Dict[str, Any]:
        """Run the Unit Test Agent."""
        start_time = time.perf_counter()
        session_id = state.get("session_id", "unknown")
        
        intent_dict = state.get("intent", {})
        request_dict = state.get("request", {})
        
        target_files = intent_dict.get("test_targets", [])
        if not target_files:
            target_files = [f["path"] for f in request_dict.get("files", [])]
        
        parser_output = ParserOutput.from_dict(state.get("parser_output", {}))
        kb_context = KBContext.from_dict(state.get("kb_context", {}))
        
        log_agent_start(logger, "UnitTestAgent", len(target_files),
                       model=self.config.llm_model or "default")
        
        result = await self.test_agent.run(
            parsed_metadata=parser_output,
            kb_context=kb_context,
            target_files=target_files,
            repo_path=request_dict.get("repo_path"),
        )
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        output_dict = result.output.to_dict() if result.output else {}
        
        tests_generated = len(output_dict.get("tests", [])) if output_dict else 0
        
        log_agent_complete(logger, "UnitTestAgent", duration_ms, {
            "status": result.status.value,
            "target_files": len(target_files),
            "tests_generated": tests_generated,
        })
        
        log_checkpoint_saved(logger, session_id, "run_tests")
        
        return {
            "test_output": output_dict,
            "test_result": result.to_dict(),
            "current_step": "tests_complete",
            "completed_steps": state.get("completed_steps", []) + ["run_tests"],
        }
    
    async def _node_aggregate(self, state: SupervisorState) -> Dict[str, Any]:
        """Aggregate all results."""
        start_time = time.perf_counter()
        session_id = state.get("session_id", "unknown")
        
        log_with_data(logger, 20, "Aggregating results from all agents", {
            "step": "aggregate",
            "completed_steps": state.get("completed_steps", []),
        })
        
        # Reconstruct agent results
        parser_result = None
        review_result = None
        test_result = None
        
        if state.get("parser_result"):
            pr = state["parser_result"]
            parser_result = AgentResult(
                agent_name=pr["agent_name"],
                status=AgentStatus(pr["status"]),
                output=ParserOutput.from_dict(state.get("parser_output", {})) if state.get("parser_output") else None,
                error=pr.get("error"),
                started_at=pr.get("started_at"),
                completed_at=pr.get("completed_at"),
                duration_seconds=pr.get("duration_seconds"),
            )
        
        if state.get("review_result"):
            rr = state["review_result"]
            review_result = AgentResult(
                agent_name=rr["agent_name"],
                status=AgentStatus(rr["status"]),
                output=ReviewOutput.from_dict(state.get("review_output", {})) if state.get("review_output") else None,
                error=rr.get("error"),
                started_at=rr.get("started_at"),
                completed_at=rr.get("completed_at"),
                duration_seconds=rr.get("duration_seconds"),
            )
        
        if state.get("test_result"):
            tr = state["test_result"]
            test_result = AgentResult(
                agent_name=tr["agent_name"],
                status=AgentStatus(tr["status"]),
                output=TestOutput.from_dict(state.get("test_output", {})) if state.get("test_output") else None,
                error=tr.get("error"),
                started_at=tr.get("started_at"),
                completed_at=tr.get("completed_at"),
                duration_seconds=tr.get("duration_seconds"),
            )
        
        # Merge results
        kb_context = KBContext.from_dict(state.get("kb_context", {})) if state.get("kb_context") else None
        intent = UserIntent.from_dict(state.get("intent", {})) if state.get("intent") else None
        
        final_output = self.aggregator.merge(
            parser_result=parser_result,
            review_result=review_result,
            test_result=test_result,
            kb_context=kb_context,
            intent=intent,
        )
        
        final_output.session_id = state.get("session_id")
        final_output.started_at = state.get("started_at")
        final_output.completed_at = datetime.utcnow().isoformat()
        
        return {
            "final_output": final_output.to_dict(),
            "current_step": "complete",
            "completed_steps": state.get("completed_steps", []) + ["aggregate"],
            "completed_at": final_output.completed_at,
        }
    
    async def _fetch_kb_context(self, request_dict: Dict[str, Any]) -> KBContext:
        """
        Fetch context from Knowledge Base.
        
        Only the Supervisor has KB access - sub-agents receive read-only excerpts.
        
        Args:
            request_dict: The review request as a dictionary
            
        Returns:
            KBContext with relevant learnings and categorized insights
        """
        if not self.config.kb_enabled:
            logger.debug("KB is disabled, returning empty context")
            return KBContext()
        
        try:
            # Extract file paths
            file_paths = [f.get("path", "") for f in request_dict.get("files", [])]
            
            # Extract code snippets from file contents (first 500 chars each)
            code_snippets = []
            for file_info in request_dict.get("files", []):
                content = file_info.get("content")
                if content:
                    code_snippets.append(content[:500])
            
            # Build PR context string
            pr_parts = []
            if request_dict.get("pr_title"):
                pr_parts.append(request_dict["pr_title"])
            if request_dict.get("pr_description"):
                pr_parts.append(request_dict["pr_description"][:300])
            pr_context = " ".join(pr_parts) if pr_parts else None
            
            # Query the KB
            kb_context = await self._kb_client.query_context(
                file_paths=file_paths,
                code_snippets=code_snippets,
                pr_context=pr_context,
                max_learnings=10,
            )
            
            # Post-process: categorize learnings into the appropriate buckets
            if kb_context.learnings:
                kb_context = self._categorize_learnings(kb_context)
            
            logger.info(
                f"Fetched KB context: {len(kb_context.learnings)} learnings, "
                f"{len(kb_context.coding_style)} style rules, "
                f"{len(kb_context.best_practices)} best practices"
            )
            
            return kb_context
            
        except Exception as e:
            logger.warning(f"Failed to fetch KB context: {e}")
            return KBContext()
    
    def _categorize_learnings(self, kb_context: KBContext) -> KBContext:
        """
        Categorize raw learnings into the appropriate KBContext fields.
        
        Uses simple keyword matching to categorize learnings.
        """
        style_keywords = ["style", "format", "naming", "convention", "indent", "spacing"]
        test_keywords = ["test", "testing", "mock", "fixture", "assert", "coverage"]
        practice_keywords = ["best practice", "should", "prefer", "avoid", "always", "never"]
        
        for learning in kb_context.learnings:
            content = learning.get("content", "").lower()
            
            # Check for style-related
            if any(kw in content for kw in style_keywords):
                kb_context.coding_style.append(learning.get("content", ""))
            
            # Check for testing-related
            elif any(kw in content for kw in test_keywords):
                kb_context.testing_patterns.append(learning.get("content", ""))
            
            # Check for best practices
            elif any(kw in content for kw in practice_keywords):
                kb_context.best_practices.append(learning.get("content", ""))
            
            # Default to conventions
            else:
                kb_context.conventions.append(learning.get("content", ""))
        
        return kb_context
    
    async def run(
        self,
        request: ReviewRequest,
        session_id: Optional[str] = None,
    ) -> SupervisorOutput:
        """
        Run the supervisor workflow on a review request.
        
        Args:
            request: The review request
            session_id: Optional session ID for checkpointing
            
        Returns:
            SupervisorOutput with aggregated results
        """
        workflow_start = time.perf_counter()
        
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        # Set session ID for log correlation
        set_session_id(session_id)
        
        # Log workflow start with full context
        log_with_data(logger, 20, "Starting supervisor workflow", {
            "session_id": session_id,
            "files_count": len(request.files),
            "repo_url": request.repo_url,
            "pr_number": request.pr_number,
            "branch": request.branch,
            "user_request": request.user_request[:100] if request.user_request else None,
            "llm_provider": self.config.llm_provider.value,
            "llm_model": self.config.llm_model,
            "kb_enabled": self.config.kb_enabled,
            "checkpointing_enabled": self.config.enable_checkpointing,
        })
        
        # Prepare initial state
        initial_state: SupervisorState = {
            "request": request.to_dict(),
            "session_id": session_id,
            "started_at": datetime.utcnow().isoformat(),
            "completed_steps": [],
            "errors": [],
            "current_step": "starting",
        }
        
        # Configure for checkpointing
        config = {"configurable": {"thread_id": session_id}}
        
        # Extract owner/repo/pr_number for checkpoint metadata
        owner = None
        repo = None
        pr_number = request.pr_number
        if request.repo_url:
            # Parse owner/repo from URL like https://github.com/owner/repo
            parts = request.repo_url.rstrip('/').split('/')
            if len(parts) >= 2:
                repo = parts[-1]
                owner = parts[-2]
        
        # Create initial checkpoint in database
        await self._save_checkpoint_to_db(
            session_id, 
            initial_state, 
            owner=owner, 
            repo=repo, 
            pr_number=pr_number
        )
        
        try:
            log_with_data(logger, 20, "Invoking LangGraph workflow", {
                "session_id": session_id,
                "entry_point": "parse_intent",
            })
            
            # Run the workflow
            final_state = await self.compiled_graph.ainvoke(
                initial_state,
                config=config,
            )
            
            workflow_duration = (time.perf_counter() - workflow_start) * 1000
            
            # Extract final output
            if final_state.get("final_output"):
                output = self._reconstruct_output(final_state["final_output"])
                output.duration_seconds = workflow_duration / 1000
                
                # Log successful completion
                log_with_data(logger, 20, "Supervisor workflow completed successfully", {
                    "session_id": session_id,
                    "status": output.status.value,
                    "total_duration_ms": round(workflow_duration, 2),
                    "steps_completed": final_state.get("completed_steps", []),
                    "review_issues": output.review_output.total_issues if output.review_output else 0,
                    "tests_generated": len(output.test_output.tests) if output.test_output else 0,
                })
                
                # Mark checkpoint as completed in database
                await self._mark_checkpoint_completed(session_id, final_state)
                
                return output
            else:
                # Something went wrong
                log_with_data(logger, 40, "Workflow completed without producing output", {
                    "session_id": session_id,
                    "final_state_keys": list(final_state.keys()) if final_state else [],
                    "completed_steps": final_state.get("completed_steps", []) if final_state else [],
                    "errors": final_state.get("errors", []) if final_state else [],
                })
                
                return SupervisorOutput(
                    status=AgentStatus.FAILED,
                    error="Workflow completed without producing output",
                    session_id=session_id,
                )
                
        except Exception as e:
            workflow_duration = (time.perf_counter() - workflow_start) * 1000
            
            log_with_data(logger, 40, f"Supervisor workflow failed: {e}", {
                "session_id": session_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(workflow_duration, 2),
            })
            
            # Mark checkpoint as failed in database
            await self._mark_checkpoint_failed(session_id, str(e))
            
            return SupervisorOutput(
                status=AgentStatus.FAILED,
                error=str(e),
                session_id=session_id,
            )
    
    async def resume(
        self,
        session_id: str,
    ) -> SupervisorOutput:
        """
        Resume a workflow from checkpoint.
        
        Args:
            session_id: The session ID to resume
            
        Returns:
            SupervisorOutput with aggregated results
        """
        set_session_id(session_id)
        
        if not self.config.enable_checkpointing:
            log_with_data(logger, 40, "Cannot resume: checkpointing is disabled", {
                "session_id": session_id,
            })
            raise ValueError("Checkpointing is not enabled")
        
        log_with_data(logger, 20, "Attempting to resume workflow from checkpoint", {
            "session_id": session_id,
        })
        
        config = {"configurable": {"thread_id": session_id}}
        
        try:
            # Try to load from database first
            db_state = await self._load_checkpoint_from_db(session_id)
            
            # Get the current state from checkpoint
            state = await self.compiled_graph.aget_state(config)
            
            if state is None and db_state is None:
                log_with_data(logger, 40, "No checkpoint found for session", {
                    "session_id": session_id,
                })
                raise ValueError(f"No checkpoint found for session: {session_id}")
            
            # Log checkpoint state
            current_step = state.values.get("current_step") if state else "unknown"
            completed_steps = state.values.get("completed_steps", []) if state else []
            
            log_checkpoint_restored(logger, session_id, current_step)
            log_with_data(logger, 20, "Checkpoint state loaded", {
                "session_id": session_id,
                "current_step": current_step,
                "completed_steps": completed_steps,
            })
            
            # Continue from where we left off
            resume_start = time.perf_counter()
            final_state = await self.compiled_graph.ainvoke(
                None,  # Continue from checkpoint
                config=config,
            )
            
            resume_duration = (time.perf_counter() - resume_start) * 1000
            
            if final_state.get("final_output"):
                output = self._reconstruct_output(final_state["final_output"])
                
                log_with_data(logger, 20, "Resumed workflow completed successfully", {
                    "session_id": session_id,
                    "status": output.status.value,
                    "resume_duration_ms": round(resume_duration, 2),
                })
                
                return output
            else:
                log_with_data(logger, 40, "Resumed workflow completed without output", {
                    "session_id": session_id,
                })
                
                return SupervisorOutput(
                    status=AgentStatus.FAILED,
                    error="Resumed workflow completed without producing output",
                    session_id=session_id,
                )
                
        except Exception as e:
            log_with_data(logger, 40, f"Resume failed: {e}", {
                "session_id": session_id,
                "error": str(e),
                "error_type": type(e).__name__,
            })
            
            return SupervisorOutput(
                status=AgentStatus.FAILED,
                error=str(e),
                session_id=session_id,
            )
    
    async def _save_checkpoint_to_db(
        self,
        session_id: str,
        state: Dict[str, Any],
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        pr_number: Optional[int] = None,
    ) -> None:
        """Save checkpoint state to database for persistence across restarts."""
        if not self.config.enable_checkpointing:
            return
        
        try:
            # Import here to avoid circular imports
            from db.database import SessionLocal
            from db import crud, schemas
            
            db = SessionLocal()
            try:
                checkpoint_data = schemas.CheckpointCreate(
                    thread_id=session_id,
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    current_node=state.get("current_step", "unknown"),
                    completed_nodes=state.get("completed_steps", []),
                    state_data=state,
                    status="in_progress",
                )
                
                crud.upsert_checkpoint(db, checkpoint_data)
                
                log_with_data(logger, 10, "Checkpoint saved to database", {
                    "session_id": session_id,
                    "current_node": checkpoint_data.current_node,
                    "completed_nodes": checkpoint_data.completed_nodes,
                })
                
            finally:
                db.close()
            
        except Exception as e:
            log_with_data(logger, 30, f"Failed to save checkpoint to database: {e}", {
                "session_id": session_id,
                "error": str(e),
            })
    
    async def _load_checkpoint_from_db(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint state from database."""
        if not self.config.enable_checkpointing:
            return None
        
        try:
            # Import here to avoid circular imports
            from db.database import SessionLocal
            from db import crud
            
            db = SessionLocal()
            try:
                checkpoint = crud.get_checkpoint_by_thread_id(db, session_id)
                
                if not checkpoint:
                    return None
                
                parsed = crud.parse_checkpoint_state(checkpoint)
                
                log_with_data(logger, 20, "Checkpoint loaded from database", {
                    "session_id": session_id,
                    "current_node": parsed.get("current_node"),
                    "status": parsed.get("status"),
                })
                
                return parsed.get("state_data")
                
            finally:
                db.close()
            
        except Exception as e:
            log_with_data(logger, 30, f"Failed to load checkpoint from database: {e}", {
                "session_id": session_id,
                "error": str(e),
            })
            return None
    
    async def _mark_checkpoint_completed(self, session_id: str, final_state: Dict[str, Any]) -> None:
        """Mark checkpoint as completed in the database."""
        if not self.config.enable_checkpointing:
            return
        
        try:
            from db.database import SessionLocal
            from db import crud
            
            db = SessionLocal()
            try:
                crud.mark_checkpoint_completed(db, session_id, final_state)
                
                log_with_data(logger, 10, "Checkpoint marked as completed", {
                    "session_id": session_id,
                })
            finally:
                db.close()
                
        except Exception as e:
            log_with_data(logger, 30, f"Failed to mark checkpoint as completed: {e}", {
                "session_id": session_id,
                "error": str(e),
            })
    
    async def _mark_checkpoint_failed(self, session_id: str, error_message: str, current_state: Optional[Dict[str, Any]] = None) -> None:
        """Mark checkpoint as failed in the database."""
        if not self.config.enable_checkpointing:
            return
        
        try:
            from db.database import SessionLocal
            from db import crud
            
            db = SessionLocal()
            try:
                crud.mark_checkpoint_failed(db, session_id, error_message, current_state)
                
                log_with_data(logger, 10, "Checkpoint marked as failed", {
                    "session_id": session_id,
                    "error": error_message,
                })
            finally:
                db.close()
                
        except Exception as e:
            log_with_data(logger, 30, f"Failed to mark checkpoint as failed: {e}", {
                "session_id": session_id,
                "error": str(e),
            })
    
    def _reconstruct_output(self, output_dict: Dict[str, Any]) -> SupervisorOutput:
        """Reconstruct SupervisorOutput from dictionary."""
        output = SupervisorOutput(
            status=AgentStatus(output_dict.get("status", "completed")),
            error=output_dict.get("error"),
            errors=output_dict.get("errors", []),
            session_id=output_dict.get("session_id"),
            checkpoint_id=output_dict.get("checkpoint_id"),
            started_at=output_dict.get("started_at"),
            completed_at=output_dict.get("completed_at"),
            duration_seconds=output_dict.get("duration_seconds"),
        )
        
        # Reconstruct nested objects
        if output_dict.get("parser_output"):
            output.parser_output = ParserOutput.from_dict(output_dict["parser_output"])
        
        if output_dict.get("review_output"):
            output.review_output = ReviewOutput.from_dict(output_dict["review_output"])
        
        if output_dict.get("test_output"):
            output.test_output = TestOutput.from_dict(output_dict["test_output"])
        
        if output_dict.get("kb_context"):
            output.kb_context = KBContext.from_dict(output_dict["kb_context"])
        
        if output_dict.get("intent"):
            output.intent = UserIntent.from_dict(output_dict["intent"])
        
        return output
    
    async def get_checkpoint_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current checkpoint state for a session.
        
        Useful for debugging or displaying progress.
        """
        if not self.config.enable_checkpointing:
            return None
        
        config = {"configurable": {"thread_id": session_id}}
        state = await self.compiled_graph.aget_state(config)
        
        return state.values if state else None


class MockSupervisorAgent(SupervisorAgent):
    """
    Mock Supervisor Agent for testing.
    
    Uses mock sub-agents and doesn't make LLM calls.
    """
    
    def __init__(self, config: Optional[SupervisorConfig] = None):
        if config is None:
            config = SupervisorConfig(use_mock_agents=True)
        else:
            config.use_mock_agents = True
        super().__init__(config)
