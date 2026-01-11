"""
Unit Test Agent

Sub-agent responsible for generating unit tests.
Only invoked when explicitly requested by user.

Responsibilities:
- Detect existing testing framework
- Generate focused unit tests for specified targets
- Follow project testing patterns from KB

Constraints:
- NEVER auto-invoked on every PR
- Only runs when user explicitly requests "generate unit tests"
- Does NOT refactor production code
- Outputs minimal, focused tests
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from .base_agent import BaseAgent, AgentConfig
from ..schemas.common import FileInfo, KBContext
from ..schemas.parser_output import ParserOutput, Symbol, SymbolType
from ..schemas.test_output import (
    TestOutput,
    GeneratedTest,
    TestFramework,
    TestType,
)
from ..llm_factory import LLMFactory, LLMProvider

logger = logging.getLogger(__name__)


from ..prompt import UNIT_TEST_SYSTEM_PROMPT


class UnitTestAgent(BaseAgent[TestOutput]):
    """
    Unit Test Agent for generating tests.
    
    ONLY invoked when explicitly requested by user.
    Never auto-invokes on PRs.
    
    Uses:
    - Knowledge Base for testing patterns
    - Parsed symbols for understanding code structure
    """
    
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        provider: LLMProvider = LLMProvider.OPENAI,
        model: Optional[str] = None,
        config: Optional[AgentConfig] = None,
    ):
        """
        Initialize the Unit Test Agent.
        
        Args:
            llm: Pre-configured LLM instance (optional)
            provider: LLM provider if llm not provided
            model: Model name if llm not provided
            config: Agent configuration
        """
        if config is None:
            config = AgentConfig(
                name="unit_test_agent",
                timeout_seconds=240.0,  # 4 minutes for test generation
                max_retries=2,
            )
        super().__init__(config)
        
        self._llm = llm
        self._provider = provider
        self._model = model
    
    @property
    def name(self) -> str:
        return "unit_test_agent"
    
    @property
    def llm(self) -> BaseChatModel:
        """Lazy-load LLM instance."""
        if self._llm is None:
            self._llm = LLMFactory.create(
                provider=self._provider,
                model=self._model,
                temperature=0.2,  # Low temperature for consistent code
            )
        return self._llm
    
    async def _execute(
        self,
        parsed_metadata: ParserOutput,
        kb_context: KBContext,
        target_files: List[str],
        repo_path: Optional[str] = None,
    ) -> TestOutput:
        """
        Generate unit tests for specified targets.
        
        Args:
            parsed_metadata: Output from Parser Agent
            kb_context: Knowledge Base context from Supervisor
            target_files: List of file paths to generate tests for
            repo_path: Repository root path for framework detection
            
        Returns:
            TestOutput with generated tests
        """
        output = TestOutput()
        
        # Detect testing framework
        framework = await self._detect_framework(repo_path, parsed_metadata)
        output.detected_framework = framework
        
        # Get testing patterns from KB
        kb_patterns = kb_context.testing_patterns if kb_context else []
        output.kb_patterns_applied = kb_patterns[:5]
        
        # Generate tests for each target file
        for target_file in target_files:
            try:
                tests = await self._generate_tests_for_file(
                    target_file,
                    parsed_metadata,
                    kb_patterns,
                    framework,
                )
                for test in tests:
                    output.add_test(test)
            except Exception as e:
                logger.warning(f"Failed to generate tests for {target_file}: {e}")
                output.warnings.append(f"Could not generate tests for {target_file}: {str(e)}")
        
        return output
    
    async def _detect_framework(
        self,
        repo_path: Optional[str],
        parsed_metadata: ParserOutput,
    ) -> TestFramework:
        """Detect the testing framework used in the project."""
        # Check file patterns
        test_files = [
            f for f in parsed_metadata.files
            if f.has_tests or any(p in f.path.lower() for p in ['test_', '_test', '.test.', '.spec.'])
        ]
        
        # Check for Python frameworks
        python_files = [f for f in parsed_metadata.files if f.language == 'python']
        if python_files:
            # Check for pytest markers
            for file_meta in test_files:
                if file_meta.language == 'python':
                    if any('@pytest' in str(s) for s in parsed_metadata.get_symbols_by_file(file_meta.path)):
                        return TestFramework.PYTEST
            return TestFramework.PYTEST  # Default for Python
        
        # Check for JS/TS frameworks
        js_ts_files = [f for f in parsed_metadata.files if f.language in ('javascript', 'typescript', 'tsx')]
        if js_ts_files:
            # Check config files
            if repo_path:
                if os.path.exists(os.path.join(repo_path, 'vitest.config.ts')):
                    return TestFramework.VITEST
                if os.path.exists(os.path.join(repo_path, 'vitest.config.js')):
                    return TestFramework.VITEST
                if os.path.exists(os.path.join(repo_path, 'jest.config.js')):
                    return TestFramework.JEST
                if os.path.exists(os.path.join(repo_path, 'jest.config.ts')):
                    return TestFramework.JEST
            return TestFramework.JEST  # Default for JS/TS
        
        return TestFramework.UNKNOWN
    
    async def _generate_tests_for_file(
        self,
        target_file: str,
        parsed_metadata: ParserOutput,
        kb_patterns: List[str],
        framework: TestFramework,
    ) -> List[GeneratedTest]:
        """Generate tests for a single file."""
        # Get symbols for the target file
        symbols = parsed_metadata.get_symbols_by_file(target_file)
        
        # Filter to testable symbols (functions, methods, classes)
        testable_symbols = [
            s for s in symbols
            if s.symbol_type in (SymbolType.FUNCTION, SymbolType.METHOD, SymbolType.CLASS)
            and not s.name.startswith('_')  # Skip private
            and s.name not in ('__init__', '__str__', '__repr__')  # Skip magic methods
        ]
        
        if not testable_symbols:
            return []
        
        # Build context
        framework_info = self._get_framework_info(framework)
        code_context = self._build_code_context(target_file, testable_symbols, parsed_metadata)
        kb_testing_patterns = "\n".join(f"- {p}" for p in kb_patterns) if kb_patterns else "No specific patterns."
        
        # Build prompt
        system_message = SystemMessage(content=UNIT_TEST_SYSTEM_PROMPT.format(
            framework_info=framework_info,
            kb_testing_patterns=kb_testing_patterns,
            code_context=code_context,
        ))
        
        human_message = HumanMessage(content=f"""Generate unit tests for the following targets in {target_file}:

{chr(10).join(f'- {s.name} ({s.symbol_type.value}, line {s.start_line})' for s in testable_symbols[:10])}

Respond with JSON only.""")
        
        # Call LLM
        try:
            response = await asyncio.to_thread(
                self.llm.invoke,
                [system_message, human_message]
            )
            
            # Parse response
            tests = self._parse_test_response(response.content, target_file, framework)
            return tests
            
        except Exception as e:
            logger.error(f"LLM test generation failed for {target_file}: {e}")
            raise
    
    def _get_framework_info(self, framework: TestFramework) -> str:
        """Get framework-specific information."""
        framework_info = {
            TestFramework.PYTEST: """Framework: pytest
- Use `def test_*()` naming
- Use `@pytest.fixture` for fixtures
- Use `pytest.raises()` for exceptions
- Use `assert` statements""",
            
            TestFramework.UNITTEST: """Framework: unittest
- Use `class Test*Case(unittest.TestCase)`
- Use `self.assertEqual`, `self.assertTrue`, etc.
- Use `self.assertRaises()` for exceptions
- Use `setUp()` and `tearDown()` methods""",
            
            TestFramework.JEST: """Framework: Jest
- Use `describe()` and `test()` or `it()`
- Use `expect().toBe()`, `expect().toEqual()`, etc.
- Use `jest.mock()` for mocking
- Use `beforeEach()` and `afterEach()` for setup""",
            
            TestFramework.VITEST: """Framework: Vitest
- Use `describe()` and `test()` or `it()`
- Use `expect().toBe()`, `expect().toEqual()`, etc.
- Use `vi.mock()` for mocking
- Use `beforeEach()` and `afterEach()` for setup""",
            
            TestFramework.MOCHA: """Framework: Mocha with Chai
- Use `describe()` and `it()`
- Use Chai's `expect().to.equal()`, etc.
- Use sinon for mocking
- Use `before()` and `after()` for setup""",
        }
        
        return framework_info.get(framework, "Unknown framework - use standard testing patterns.")
    
    def _build_code_context(
        self,
        target_file: str,
        symbols: List[Symbol],
        parsed_metadata: ParserOutput,
    ) -> str:
        """Build code context for test generation."""
        parts = [f"**File:** {target_file}", ""]
        
        # Get file metadata
        for file_meta in parsed_metadata.files:
            if file_meta.path == target_file:
                parts.append(f"**Language:** {file_meta.language}")
                parts.append("")
                break
        
        # Add symbol details
        parts.append("**Symbols to test:**")
        for sym in symbols[:10]:  # Limit to 10
            parts.append(f"\n### {sym.name}")
            parts.append(f"- Type: {sym.symbol_type.value}")
            parts.append(f"- Line: {sym.start_line}")
            if sym.parameters:
                parts.append(f"- Parameters: {', '.join(sym.parameters)}")
            if sym.return_type:
                parts.append(f"- Returns: {sym.return_type}")
            if sym.complexity:
                parts.append(f"- Complexity: {sym.complexity}")
        
        return "\n".join(parts)
    
    def _parse_test_response(
        self,
        response_content: str,
        target_file: str,
        framework: TestFramework,
    ) -> List[GeneratedTest]:
        """Parse LLM response into GeneratedTest objects."""
        tests = []
        
        try:
            # Try to extract JSON from response
            content = response_content
            if isinstance(content, list):
                content = str(content[0]) if content else ""
            content = content.strip()
            
            # Handle markdown code blocks
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            # Parse JSON
            data = json.loads(content)
            
            if not isinstance(data, list):
                data = [data]
            
            # Determine test file path
            test_file = self._determine_test_file_path(target_file, framework)
            
            for item in data:
                try:
                    test = GeneratedTest(
                        target=item.get("target", "unknown"),
                        target_file=target_file,
                        test_file=test_file,
                        test_code=item.get("test_code", ""),
                        test_name=item.get("test_name", f"test_{item.get('target', 'unknown')}"),
                        test_type=self._parse_test_type(item.get("test_type")),
                        framework=framework,
                        imports_required=item.get("imports_required", []),
                        mocks_required=item.get("mocks_required", []),
                        description=item.get("description"),
                    )
                    tests.append(test)
                except Exception as e:
                    logger.warning(f"Failed to parse test: {e}")
                    continue
                    
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
        
        return tests
    
    def _parse_test_type(self, test_type_str: Optional[str]) -> TestType:
        """Parse test type string to enum."""
        if not test_type_str:
            return TestType.UNIT
        
        type_map = {
            "unit": TestType.UNIT,
            "integration": TestType.INTEGRATION,
            "edge_case": TestType.EDGE_CASE,
            "edge-case": TestType.EDGE_CASE,
            "error_case": TestType.ERROR_CASE,
            "error-case": TestType.ERROR_CASE,
            "happy_path": TestType.HAPPY_PATH,
            "happy-path": TestType.HAPPY_PATH,
        }
        
        return type_map.get(test_type_str.lower().replace(" ", "_"), TestType.UNIT)
    
    def _determine_test_file_path(
        self,
        target_file: str,
        framework: TestFramework,
    ) -> str:
        """Determine the test file path based on conventions."""
        path = Path(target_file)
        stem = path.stem
        suffix = path.suffix
        
        if framework in (TestFramework.PYTEST, TestFramework.UNITTEST):
            # Python: test_<filename>.py in tests/ directory
            return f"tests/test_{stem}.py"
        
        elif framework in (TestFramework.JEST, TestFramework.VITEST, TestFramework.MOCHA):
            # JS/TS: <filename>.test.ts or __tests__/<filename>.test.ts
            if suffix in ('.ts', '.tsx'):
                return f"__tests__/{stem}.test.ts"
            else:
                return f"__tests__/{stem}.test.js"
        
        return f"tests/test_{stem}{suffix}"


class MockUnitTestAgent(UnitTestAgent):
    """
    Mock Unit Test Agent for testing.
    
    Returns predefined tests without making LLM calls.
    """
    
    def __init__(
        self,
        mock_tests: Optional[List[Dict[str, Any]]] = None,
        config: Optional[AgentConfig] = None,
    ):
        super().__init__(config=config)
        self._mock_tests = mock_tests or []
    
    async def _execute(
        self,
        parsed_metadata: ParserOutput,
        kb_context: KBContext,
        target_files: List[str],
        repo_path: Optional[str] = None,
    ) -> TestOutput:
        """Return mock tests without LLM call."""
        output = TestOutput()
        output.detected_framework = TestFramework.PYTEST
        
        # Add predefined mock tests
        for test_dict in self._mock_tests:
            test = GeneratedTest(
                target=test_dict.get("target", "mock_function"),
                target_file=test_dict.get("target_file", "mock_file.py"),
                test_file=test_dict.get("test_file", "tests/test_mock.py"),
                test_code=test_dict.get("test_code", "def test_mock(): pass"),
                test_name=test_dict.get("test_name", "test_mock"),
                framework=TestFramework.PYTEST,
            )
            output.add_test(test)
        
        # Generate basic tests for symbols
        for target_file in target_files:
            functions = [
                s for s in parsed_metadata.get_symbols_by_file(target_file)
                if s.symbol_type == SymbolType.FUNCTION
            ]
            
            for func in functions[:5]:  # Limit to 5
                test = GeneratedTest(
                    target=func.name,
                    target_file=target_file,
                    test_file=f"tests/test_{Path(target_file).stem}.py",
                    test_code=f"def test_{func.name}():\n    # TODO: Implement test\n    pass",
                    test_name=f"test_{func.name}",
                    framework=TestFramework.PYTEST,
                    description=f"Unit test for {func.name}",
                )
                output.add_test(test)
        
        return output
