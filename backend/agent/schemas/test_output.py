"""
Unit Test Agent Output Schemas

Defines structured output types for the Unit Test Agent which handles:
- Test generation for specified files/functions
- Framework-aware test creation
- Coverage-focused test design
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any


class TestFramework(str, Enum):
    """Supported testing frameworks."""
    # Python
    PYTEST = "pytest"
    UNITTEST = "unittest"
    # JavaScript/TypeScript
    JEST = "jest"
    VITEST = "vitest"
    MOCHA = "mocha"
    # Unknown/Auto-detect
    UNKNOWN = "unknown"


class TestType(str, Enum):
    """Types of tests that can be generated."""
    UNIT = "unit"
    INTEGRATION = "integration"
    EDGE_CASE = "edge_case"
    ERROR_CASE = "error_case"
    HAPPY_PATH = "happy_path"


@dataclass
class GeneratedTest:
    """
    A single generated unit test.
    
    Contains the test code and metadata about what it tests.
    """
    target: str  # Function/method/class being tested
    target_file: str  # Source file path
    test_file: str  # Suggested test file path
    test_code: str  # The actual test code
    test_name: str  # Name of the test function/class
    test_type: TestType = TestType.UNIT
    framework: TestFramework = TestFramework.PYTEST
    
    # Coverage information
    covers_happy_path: bool = True
    covers_edge_cases: bool = False
    covers_error_cases: bool = False
    
    # Dependencies
    imports_required: List[str] = field(default_factory=list)
    mocks_required: List[str] = field(default_factory=list)
    fixtures_required: List[str] = field(default_factory=list)
    
    # Metadata
    description: Optional[str] = None
    estimated_coverage: Optional[float] = None  # 0.0 to 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "target_file": self.target_file,
            "test_file": self.test_file,
            "test_code": self.test_code,
            "test_name": self.test_name,
            "test_type": self.test_type.value,
            "framework": self.framework.value,
            "covers_happy_path": self.covers_happy_path,
            "covers_edge_cases": self.covers_edge_cases,
            "covers_error_cases": self.covers_error_cases,
            "imports_required": self.imports_required,
            "mocks_required": self.mocks_required,
            "fixtures_required": self.fixtures_required,
            "description": self.description,
            "estimated_coverage": self.estimated_coverage,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeneratedTest":
        """Reconstruct GeneratedTest from dictionary."""
        return cls(
            target=data["target"],
            target_file=data["target_file"],
            test_file=data["test_file"],
            test_code=data["test_code"],
            test_name=data["test_name"],
            test_type=TestType(data.get("test_type", "unit")),
            framework=TestFramework(data.get("framework", "pytest")),
            covers_happy_path=data.get("covers_happy_path", True),
            covers_edge_cases=data.get("covers_edge_cases", False),
            covers_error_cases=data.get("covers_error_cases", False),
            imports_required=data.get("imports_required", []),
            mocks_required=data.get("mocks_required", []),
            fixtures_required=data.get("fixtures_required", []),
            description=data.get("description"),
            estimated_coverage=data.get("estimated_coverage"),
        )


@dataclass
class TestFileSummary:
    """Summary of tests generated for a single target file."""
    target_file: str
    test_file: str
    test_count: int
    framework: TestFramework
    targets_covered: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_file": self.target_file,
            "test_file": self.test_file,
            "test_count": self.test_count,
            "framework": self.framework.value,
            "targets_covered": self.targets_covered,
        }


@dataclass
class TestOutput:
    """
    Complete output from the Unit Test Agent.
    
    Contains all generated tests and summary information.
    
    Example:
    {
        "tests": [
            {
                "target": "calculate_total",
                "test_file": "tests/test_utils.py",
                "test_code": "def test_calculate_total_happy_path():..."
            }
        ]
    }
    """
    tests: List[GeneratedTest] = field(default_factory=list)
    
    # Summary information
    total_tests: int = 0
    files_covered: int = 0
    file_summaries: List[TestFileSummary] = field(default_factory=list)
    
    # Detected framework information
    detected_framework: TestFramework = TestFramework.UNKNOWN
    existing_test_patterns: List[str] = field(default_factory=list)  # e.g., "test_*.py"
    
    # KB-related
    kb_patterns_applied: List[str] = field(default_factory=list)
    
    # Any warnings or notes
    warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate summary statistics."""
        self._recalculate_stats()
    
    def _recalculate_stats(self):
        """Recalculate summary statistics."""
        self.total_tests = len(self.tests)
        
        # Group by target file
        file_tests: Dict[str, List[GeneratedTest]] = {}
        for test in self.tests:
            if test.target_file not in file_tests:
                file_tests[test.target_file] = []
            file_tests[test.target_file].append(test)
        
        self.files_covered = len(file_tests)
        
        # Build file summaries
        self.file_summaries = []
        for target_file, tests in file_tests.items():
            # Use first test's info for summary
            test_file = tests[0].test_file if tests else ""
            framework = tests[0].framework if tests else TestFramework.UNKNOWN
            
            summary = TestFileSummary(
                target_file=target_file,
                test_file=test_file,
                test_count=len(tests),
                framework=framework,
                targets_covered=[t.target for t in tests],
            )
            self.file_summaries.append(summary)
    
    def add_test(self, test: GeneratedTest):
        """Add a test and recalculate stats."""
        self.tests.append(test)
        self._recalculate_stats()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tests": [t.to_dict() for t in self.tests],
            "total_tests": self.total_tests,
            "files_covered": self.files_covered,
            "file_summaries": [s.to_dict() for s in self.file_summaries],
            "detected_framework": self.detected_framework.value,
            "existing_test_patterns": self.existing_test_patterns,
            "kb_patterns_applied": self.kb_patterns_applied,
            "warnings": self.warnings,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestOutput":
        """Reconstruct TestOutput from dictionary (for checkpointing)."""
        output = cls(
            tests=[GeneratedTest.from_dict(t) for t in data.get("tests", [])],
            detected_framework=TestFramework(data.get("detected_framework", "unknown")),
            existing_test_patterns=data.get("existing_test_patterns", []),
            kb_patterns_applied=data.get("kb_patterns_applied", []),
            warnings=data.get("warnings", []),
        )
        return output
    
    def get_tests_by_file(self, target_file: str) -> List[GeneratedTest]:
        """Get all tests for a specific target file."""
        return [t for t in self.tests if t.target_file == target_file]
    
    def get_test_code_for_file(self, test_file: str) -> str:
        """Get combined test code for a test file."""
        tests = [t for t in self.tests if t.test_file == test_file]
        if not tests:
            return ""
        
        # Combine imports
        all_imports = set()
        for test in tests:
            all_imports.update(test.imports_required)
        
        # Build complete test file
        parts = []
        
        # Imports
        if all_imports:
            parts.extend(sorted(all_imports))
            parts.append("")
        
        # Test code
        for test in tests:
            parts.append(test.test_code)
            parts.append("")
        
        return "\n".join(parts)
    
    def to_summary_text(self) -> str:
        """Generate a summary text for the test generation."""
        parts = [
            "## Unit Test Generation Summary",
            "",
            f"Generated **{self.total_tests}** test(s) for **{self.files_covered}** file(s).",
            "",
        ]
        
        if self.detected_framework != TestFramework.UNKNOWN:
            parts.append(f"**Framework:** {self.detected_framework.value}")
            parts.append("")
        
        if self.file_summaries:
            parts.append("### Files Covered")
            parts.append("")
            for summary in self.file_summaries:
                parts.append(f"- `{summary.target_file}` -> `{summary.test_file}` ({summary.test_count} tests)")
            parts.append("")
        
        if self.warnings:
            parts.append("### Warnings")
            parts.append("")
            for warning in self.warnings:
                parts.append(f"- {warning}")
            parts.append("")
        
        if self.kb_patterns_applied:
            parts.append("### Applied Testing Patterns")
            parts.append("")
            for pattern in self.kb_patterns_applied[:5]:
                parts.append(f"- {pattern}")
            parts.append("")
        
        return "\n".join(parts)
