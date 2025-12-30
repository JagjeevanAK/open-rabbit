"""
Intent Parser

Parses user requests to determine which agents to invoke.

Handles intents:
- review only (default)
- review + tests (explicit request)
- tests only (explicit request)
"""

import re
import logging
from typing import Optional, List

from ..schemas.common import UserIntent, IntentType, ReviewRequest

logger = logging.getLogger(__name__)


# Patterns for detecting test generation requests
TEST_REQUEST_PATTERNS = [
    r"generate\s+(unit\s+)?tests?",
    r"write\s+(unit\s+)?tests?",
    r"create\s+(unit\s+)?tests?",
    r"add\s+(unit\s+)?tests?",
    r"need\s+(unit\s+)?tests?",
    r"want\s+(unit\s+)?tests?",
    r"with\s+(unit\s+)?tests?",
    r"include\s+(unit\s+)?tests?",
    r"\btest\s+generation\b",
    r"\bunit\s+test\b",
]

# Patterns for detecting test-only requests (no review)
TEST_ONLY_PATTERNS = [
    r"^generate\s+(unit\s+)?tests?\s+(for|only)",
    r"^only\s+(generate|write|create)\s+tests?",
    r"^tests?\s+only",
    r"^just\s+(generate|write|create)\s+tests?",
]

# Patterns for detecting review-only requests (no tests)
REVIEW_ONLY_PATTERNS = [
    r"^review\s+only",
    r"^only\s+review",
    r"^just\s+review",
    r"^no\s+tests?",
    r"without\s+tests?",
    r"skip\s+tests?",
]

# Patterns for detecting specific file targets for tests
TARGET_PATTERNS = [
    r"tests?\s+for\s+[`'\"]?([^`'\"]+)[`'\"]?",
    r"test\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)",
]


class IntentParser:
    """
    Parses user requests to determine intent.
    
    Intent determines:
    - Whether to run code review (default: yes)
    - Whether to generate tests (only if explicitly requested)
    - Which files/functions to target for tests
    """
    
    def __init__(self):
        """Initialize the intent parser with compiled patterns."""
        self._test_patterns = [re.compile(p, re.IGNORECASE) for p in TEST_REQUEST_PATTERNS]
        self._test_only_patterns = [re.compile(p, re.IGNORECASE) for p in TEST_ONLY_PATTERNS]
        self._review_only_patterns = [re.compile(p, re.IGNORECASE) for p in REVIEW_ONLY_PATTERNS]
        self._target_patterns = [re.compile(p, re.IGNORECASE) for p in TARGET_PATTERNS]
    
    def parse(self, request: ReviewRequest) -> UserIntent:
        """
        Parse a review request to determine user intent.
        
        Args:
            request: The review request containing user_request text
            
        Returns:
            UserIntent with parsed intent type and options
        """
        user_request = request.user_request or ""
        
        # Default intent: review only
        intent = UserIntent(
            intent_type=IntentType.REVIEW_ONLY,
            should_review=True,
            should_generate_tests=False,
            review_scope="diff" if any(f.diff for f in request.files) else "full_file",
            raw_request=user_request,
        )
        
        if not user_request:
            return intent
        
        # Check for test-only requests
        if self._matches_any(user_request, self._test_only_patterns):
            intent.intent_type = IntentType.TESTS_ONLY
            intent.should_review = False
            intent.should_generate_tests = True
            intent.test_targets = self._extract_targets(user_request, request)
            logger.info(f"Parsed intent: TESTS_ONLY for targets {intent.test_targets}")
            return intent
        
        # Check for review-only requests
        if self._matches_any(user_request, self._review_only_patterns):
            intent.intent_type = IntentType.REVIEW_ONLY
            intent.should_review = True
            intent.should_generate_tests = False
            logger.info("Parsed intent: REVIEW_ONLY")
            return intent
        
        # Check for test generation request (combined with review)
        if self._matches_any(user_request, self._test_patterns):
            intent.intent_type = IntentType.REVIEW_AND_TESTS
            intent.should_review = True
            intent.should_generate_tests = True
            intent.test_targets = self._extract_targets(user_request, request)
            logger.info(f"Parsed intent: REVIEW_AND_TESTS for targets {intent.test_targets}")
            return intent
        
        logger.info("Parsed intent: REVIEW_ONLY (default)")
        return intent
    
    def _matches_any(self, text: str, patterns: List[re.Pattern]) -> bool:
        """Check if text matches any of the patterns."""
        return any(p.search(text) for p in patterns)
    
    def _extract_targets(
        self,
        user_request: str,
        request: ReviewRequest
    ) -> List[str]:
        """Extract specific targets for test generation."""
        targets = []
        
        # Try to extract targets from request text
        for pattern in self._target_patterns:
            matches = pattern.findall(user_request)
            for match in matches:
                if match and match not in targets:
                    targets.append(match)
        
        # If no specific targets, use all changed files
        if not targets and request.files:
            targets = [f.path for f in request.files if not f.is_deleted]
        
        return targets
    
    @staticmethod
    def should_generate_tests(user_request: Optional[str]) -> bool:
        """
        Quick check if user explicitly requested test generation.
        
        This is used to enforce the "never auto-invoke" rule.
        Tests are ONLY generated when explicitly requested.
        """
        if not user_request:
            return False
        
        user_request_lower = user_request.lower()
        
        # Must contain explicit test generation keywords
        test_keywords = [
            "generate test",
            "write test",
            "create test",
            "add test",
            "unit test",
            "test generation",
            "need test",
            "want test",
        ]
        
        return any(kw in user_request_lower for kw in test_keywords)
    
    def parse_from_text(self, text: str) -> UserIntent:
        """
        Parse intent from just a text string.
        
        Convenience method for simple cases.
        """
        from ..schemas.common import FileInfo
        
        dummy_request = ReviewRequest(
            files=[],
            user_request=text,
        )
        return self.parse(dummy_request)
