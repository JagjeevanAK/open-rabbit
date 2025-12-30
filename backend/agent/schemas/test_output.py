"""
Unit Test Agent Output Schemas

Defines the output structures for the Unit Test Agent including:
- Test framework detection
- Generated test structures
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

from .common import FileChange
from .parser_output import FileAnalysis, FunctionInfo


class TestFramework(str, Enum):
    """Supported testing frameworks"""
    PYTEST = "pytest"
    UNITTEST = "unittest"
    JEST = "jest"
    VITEST = "vitest"
    MOCHA = "mocha"
    UNKNOWN = "unknown"


class TestType(str, Enum):
    """Types of tests"""
    UNIT = "unit"
    INTEGRATION = "integration"
    EDGE_CASE = "edge_case"
    ERROR_HANDLING = "error_handling"


class GeneratedTest(BaseModel):
    """A generated test case"""
    function_name: str = Field(..., description="Name of the function being tested")
    test_name: str = Field(..., description="Name of the test function")
    test_type: TestType
    test_code: str
    
    # Source info
    source_file: str
    source_line: int
    
    # Metadata
    description: Optional[str] = None
    setup_required: bool = False
    mocks_required: List[str] = Field(default_factory=list)
    
    # Validation
    syntax_valid: bool = Field(default=True)
    validation_error: Optional[str] = None


class TestInput(BaseModel):
    """Input to the Unit Test Agent"""
    changed_files: List[FileChange]
    repo_path: str
    
    # Parser output for context
    parser_outputs: Dict[str, FileAnalysis] = Field(default_factory=dict)
    
    # Configuration
    framework: Optional[TestFramework] = Field(default=None, description="Override detected framework")
    max_tests_per_function: int = Field(default=3)
    include_edge_cases: bool = Field(default=True)
    include_error_handling: bool = Field(default=True)


class TestOutput(BaseModel):
    """Output from the Unit Test Agent"""
    framework: TestFramework
    tests: List[GeneratedTest] = Field(default_factory=list)
    
    # Statistics
    functions_covered: int = Field(default=0)
    total_tests_generated: int = Field(default=0)
    
    # Functions that couldn't have tests generated
    skipped_functions: List[str] = Field(default_factory=list)
    skip_reasons: Dict[str, str] = Field(default_factory=dict)
    
    # Test file content (ready to write)
    test_files: Dict[str, str] = Field(default_factory=dict, description="file_path -> content")
    
    def get_tests_for_file(self, file_path: str) -> List[GeneratedTest]:
        """Get tests for a specific source file"""
        return [t for t in self.tests if t.source_file == file_path]
