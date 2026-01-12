"""
LLM-as-a-Judge Evaluator

Uses an LLM to evaluate agent outputs for quality, accuracy, and completeness.
"""

import os
from typing import Optional
from dataclasses import dataclass

from langfuse import Langfuse

from ..logging_config import get_logger
from ..langfuse_integration import get_langfuse_client, score_trace

logger = get_logger(__name__)


@dataclass
class EvalResult:
    """Result from an LLM evaluation."""
    score: float  # 0.0 - 1.0
    reasoning: str
    evaluation_type: str


class LLMJudgeEvaluator:
    """
    LLM-as-a-Judge evaluator that uses GPT-4 to score outputs.
    
    Can be configured in Langfuse UI or run programmatically.
    """
    
    QUALITY_PROMPT = """You are an expert evaluator for AI agent outputs.
    
Evaluate the following agent response on a scale of 0-10 based on:
1. Accuracy: Is the information correct and factual?
2. Completeness: Does it fully address the request?
3. Clarity: Is the response clear and well-structured?
4. Actionability: Are suggestions specific and actionable?

Response to evaluate:
{response}

Original request:
{request}

Provide your evaluation in this format:
SCORE: [0-10]
REASONING: [Your detailed reasoning]
"""

    CODE_REVIEW_PROMPT = """You are an expert code reviewer evaluating the quality of an AI-generated code review.

Evaluate the code review on a scale of 0-10 based on:
1. Issue Detection: Did it catch real issues?
2. Severity Assessment: Are severity levels appropriate?
3. Actionability: Are fixes specific and implementable?
4. False Positives: Does it avoid flagging non-issues?

Code Review Output:
{review}

Original Code:
{code}

Provide your evaluation in this format:
SCORE: [0-10]
REASONING: [Your detailed reasoning]
"""

    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self._openai_client = None
    
    @property
    def openai_client(self):
        """Lazy-load OpenAI client."""
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI()
        return self._openai_client
    
    def evaluate(
        self,
        prompt_template: str,
        variables: dict,
        trace_id: Optional[str] = None,
        score_name: str = "llm-judge",
    ) -> EvalResult:
        """
        Run an LLM evaluation.
        
        Args:
            prompt_template: Prompt template with {variable} placeholders
            variables: Variables to fill in the template
            trace_id: Optional Langfuse trace ID to attach score
            score_name: Name for the score in Langfuse
            
        Returns:
            EvalResult with score and reasoning
        """
        try:
            prompt = prompt_template.format(**variables)
            
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            
            result_text = response.choices[0].message.content
            
            # Parse score from response
            score = self._parse_score(result_text)
            
            eval_result = EvalResult(
                # Normalize to 0-1
                score=score / 10.0,  
                reasoning=result_text,
                evaluation_type=score_name,
            )
            
            # Log to Langfuse if trace_id provided
            if trace_id:
                score_trace(
                    trace_id=trace_id,
                    name=score_name,
                    value=eval_result.score,
                    comment=eval_result.reasoning[:500],
                )
            
            return eval_result
            
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
            return EvalResult(
                score=0.0,
                reasoning=f"Evaluation failed: {e}",
                evaluation_type=score_name,
            )
    
    def _parse_score(self, text: str) -> float:
        """Extract score from LLM response."""
        import re
        match = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if match:
            return min(10.0, max(0.0, float(match.group(1))))
        # Default middle score if parsing fails
        return 5.0  


def evaluate_with_llm(
    response: str,
    request: str,
    trace_id: Optional[str] = None,
    evaluation_type: str = "quality",
) -> EvalResult:
    """
    Convenience function to evaluate a response using LLM-as-a-Judge.
    
    Args:
        response: The agent's response to evaluate
        request: The original user request
        trace_id: Optional Langfuse trace ID
        evaluation_type: Type of evaluation ("quality" or "code_review")
        
    Returns:
        EvalResult with score and reasoning
    """
    evaluator = LLMJudgeEvaluator()
    
    if evaluation_type == "code_review":
        return evaluator.evaluate(
            LLMJudgeEvaluator.CODE_REVIEW_PROMPT,
            {"review": response, "code": request},
            trace_id=trace_id,
            score_name="code-review-quality",
        )
    else:
        return evaluator.evaluate(
            LLMJudgeEvaluator.QUALITY_PROMPT,
            {"response": response, "request": request},
            trace_id=trace_id,
            score_name="response-quality",
        )
