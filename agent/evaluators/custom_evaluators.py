"""
Custom Code Evaluators

Programmatic evaluators for assessing agent output quality without LLM calls.
"""

from typing import Optional
from dataclasses import dataclass

from ..schemas.common import SupervisorOutput, AgentStatus
from ..schemas.review_output import ReviewOutput, Severity
from ..schemas.test_output import TestOutput
from ..langfuse_integration import score_trace
from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass 
class EvalScore:
    """Score from a custom evaluator."""
    name: str
    value: float  # 0.0 - 1.0
    details: str


def evaluate_response_quality(
    output: SupervisorOutput,
    trace_id: Optional[str] = None,
) -> EvalScore:
    """
    Evaluate overall response quality based on completion status.
    
    Checks:
    - Did the agent complete successfully?
    - Were there any errors?
    - Did all requested agents run?
    """
    score = 1.0
    details = []
    
    # Check completion status
    if output.status != AgentStatus.COMPLETED:
        score -= 0.5
        details.append(f"Agent did not complete (status: {output.status})")
    
    # Check for errors
    if output.errors:
        penalty = min(0.3, len(output.errors) * 0.1)
        score -= penalty
        details.append(f"Encountered {len(output.errors)} errors")
    
    # Check that expected outputs exist
    if output.review_output is None and output.test_output is None:
        score -= 0.2
        details.append("No review or test output generated")
    
    score = max(0.0, score)
    detail_str = "; ".join(details) if details else "All checks passed"
    
    if trace_id:
        score_trace(trace_id, "response-completeness", score, detail_str)
    
    return EvalScore(name="response-completeness", value=score, details=detail_str)


def evaluate_code_review_quality(
    review_output: Optional[ReviewOutput],
    trace_id: Optional[str] = None,
) -> EvalScore:
    """
    Evaluate code review quality based on issue characteristics.
    
    Checks:
    - Issue count and distribution
    - Severity balance
    - Actionability (issues have file/line references)
    """
    if review_output is None:
        return EvalScore(
            name="code-review-quality",
            value=0.0,
            details="No review output"
        )
    
    issues = review_output.issues
    if not issues:
        # No issues could be good (clean code) or suspicious
        return EvalScore(
            name="code-review-quality",
            value=0.7,
            details="No issues found (could be clean code)"
        )
    
    score = 1.0
    details = []
    
    # Check issue actionability (has file + line + message)
    actionable_count = sum(
        1 for i in issues 
        if i.file and i.line and i.message and len(i.message) > 10
    )
    actionability = actionable_count / len(issues)
    if actionability < 0.8:
        score -= 0.2
        details.append(f"Only {actionability:.0%} issues are actionable")
    
    # Check severity distribution
    severity_counts = {}
    for issue in issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
    
    # Penalize if all issues same severity (suspicious)
    if len(severity_counts) == 1 and len(issues) > 3:
        score -= 0.1
        details.append("All issues have same severity")
    
    # Check for reasonable issue count
    if len(issues) > 50:
        score -= 0.2
        details.append(f"Too many issues ({len(issues)})")
    
    score = max(0.0, score)
    detail_str = "; ".join(details) if details else f"Found {len(issues)} actionable issues"
    
    if trace_id:
        score_trace(trace_id, "code-review-quality", score, detail_str)
    
    return EvalScore(name="code-review-quality", value=score, details=detail_str)


def evaluate_test_quality(
    test_output: Optional[TestOutput],
    trace_id: Optional[str] = None,
) -> EvalScore:
    """
    Evaluate generated test quality.
    
    Checks:
    - Tests were generated
    - Tests have meaningful names
    - Tests cover different scenarios
    """
    if test_output is None:
        return EvalScore(
            name="test-quality",
            value=0.0,
            details="No test output"
        )
    
    tests = test_output.tests
    if not tests:
        return EvalScore(
            name="test-quality",
            value=0.0,
            details="No tests generated"
        )
    
    score = 1.0
    details = []
    
    # Check test names are meaningful (not generic)
    generic_names = ["test1", "test2", "test_function", "test_method"]
    meaningful_count = sum(
        1 for t in tests 
        if t.name.lower() not in generic_names and len(t.name) > 5
    )
    if meaningful_count < len(tests):
        score -= 0.2
        details.append("Some tests have generic names")
    
    # Check test code exists and is substantial
    substantial_tests = sum(
        1 for t in tests 
        if t.code and len(t.code) > 50
    )
    if substantial_tests < len(tests) * 0.8:
        score -= 0.2
        details.append("Some tests lack substantial code")
    
    score = max(0.0, score)
    detail_str = "; ".join(details) if details else f"Generated {len(tests)} quality tests"
    
    if trace_id:
        score_trace(trace_id, "test-quality", score, detail_str)
    
    return EvalScore(name="test-quality", value=score, details=detail_str)


def run_all_evaluators(
    output: SupervisorOutput,
    trace_id: Optional[str] = None,
) -> list[EvalScore]:
    """
    Run all custom evaluators on a supervisor output.
    
    Args:
        output: The supervisor output to evaluate
        trace_id: Optional Langfuse trace ID for scoring
        
    Returns:
        List of evaluation scores
    """
    scores = []
    
    # Response quality
    scores.append(evaluate_response_quality(output, trace_id))
    
    # Code review quality (if available)
    if output.review_output:
        scores.append(evaluate_code_review_quality(output.review_output, trace_id))
    
    # Test quality (if available)
    if output.test_output:
        scores.append(evaluate_test_quality(output.test_output, trace_id))
    
    logger.info(
        f"Evaluation complete: {', '.join(f'{s.name}={s.value:.2f}' for s in scores)}"
    )
    
    return scores
