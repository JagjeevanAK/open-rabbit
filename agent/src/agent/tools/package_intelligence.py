"""
Package Intelligence Tool for Code Review Agent.

Detects package version changes from diffs, identifies new imports,
and builds context for the review agent about package updates.

Supports:
- npm/JavaScript/TypeScript (package.json)
- Python/pip (requirements.txt, pyproject.toml, setup.py)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import tool

from .web_search import (
    search_package_breaking_changes,
    search_package_deprecations,
    search_new_package_apis,
    search_python_package_changes,
    is_search_enabled,
)

logger = logging.getLogger(__name__)


class PackageEcosystem(str, Enum):
    """Supported package ecosystems."""
    NPM = "npm"
    PYTHON = "python"
    UNKNOWN = "unknown"


@dataclass
class VersionChange:
    """Represents a version change for a package."""
    package_name: str
    old_version: Optional[str]
    new_version: Optional[str]
    ecosystem: PackageEcosystem
    change_type: str  # 'added', 'removed', 'upgraded', 'downgraded'
    is_major_change: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "package": self.package_name,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "ecosystem": self.ecosystem.value,
            "change_type": self.change_type,
            "is_major_change": self.is_major_change
        }


@dataclass
class NewImport:
    """Represents a new import detected in code."""
    import_path: str
    file_path: str
    ecosystem: PackageEcosystem
    is_external: bool = True


@dataclass
class PackageIntelligenceResult:
    """Result from package intelligence analysis."""
    version_changes: List[VersionChange] = field(default_factory=list)
    new_imports: List[NewImport] = field(default_factory=list)
    files_analyzed: List[str] = field(default_factory=list)
    context_summary: str = ""
    
    def has_changes(self) -> bool:
        return bool(self.version_changes or self.new_imports)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_changes": [v.to_dict() for v in self.version_changes],
            "new_imports": [
                {"import": i.import_path, "file": i.file_path, "ecosystem": i.ecosystem.value}
                for i in self.new_imports
            ],
            "files_analyzed": self.files_analyzed,
            "has_changes": self.has_changes()
        }


def _parse_semver(version: str) -> Tuple[int, int, int]:
    """Parse a semver string into (major, minor, patch) tuple."""
    # Remove common prefixes
    version = version.lstrip("^~>=<v")
    
    # Handle complex version ranges - just take the first version
    version = version.split(" ")[0].split("||")[0].split(",")[0].strip()
    
    # Extract numeric parts
    match = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", version)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2) or 0)
        patch = int(match.group(3) or 0)
        return (major, minor, patch)
    
    return (0, 0, 0)


def _is_major_version_change(old_version: str, new_version: str) -> bool:
    """Check if this is a major version change."""
    if not old_version or not new_version:
        return False
    
    try:
        old_parsed = _parse_semver(old_version)
        new_parsed = _parse_semver(new_version)
        return old_parsed[0] != new_parsed[0]
    except Exception:
        return False


def _determine_change_type(old_version: Optional[str], new_version: Optional[str]) -> str:
    """Determine the type of version change."""
    if not old_version and new_version:
        return "added"
    if old_version and not new_version:
        return "removed"
    if not old_version or not new_version:
        return "unknown"
    
    try:
        old_parsed = _parse_semver(old_version)
        new_parsed = _parse_semver(new_version)
        
        if old_parsed < new_parsed:
            return "upgraded"
        elif old_parsed > new_parsed:
            return "downgraded"
        else:
            return "unchanged"
    except Exception:
        return "changed"


def parse_package_json_diff(diff_content: str) -> List[VersionChange]:
    """
    Parse package.json diff to extract version changes.
    
    Args:
        diff_content: The diff content for package.json
        
    Returns:
        List of version changes detected
    """
    changes: List[VersionChange] = []
    
    # Track removed and added packages
    removed_packages: Dict[str, str] = {}
    added_packages: Dict[str, str] = {}
    
    # Pattern to match package entries in package.json
    # Handles: "package-name": "^1.0.0" or "package-name": "1.0.0"
    package_pattern = re.compile(r'"([^"]+)":\s*"([^"]+)"')
    
    for line in diff_content.split("\n"):
        line = line.strip()
        
        # Skip non-diff lines
        if not line.startswith(("-", "+")) or line.startswith(("---", "+++")):
            continue
        
        match = package_pattern.search(line)
        if not match:
            continue
        
        package_name = match.group(1)
        version = match.group(2)
        
        # Skip non-version entries (scripts, config, etc.)
        if not re.search(r"\d", version):
            continue
        
        if line.startswith("-") and not line.startswith("---"):
            removed_packages[package_name] = version
        elif line.startswith("+") and not line.startswith("+++"):
            added_packages[package_name] = version
    
    # Process the changes
    all_packages = set(removed_packages.keys()) | set(added_packages.keys())
    
    for package_name in all_packages:
        old_version = removed_packages.get(package_name)
        new_version = added_packages.get(package_name)
        
        change_type = _determine_change_type(old_version, new_version)
        
        if change_type in ("unchanged",):
            continue
        
        is_major = _is_major_version_change(old_version or "", new_version or "")
        
        changes.append(VersionChange(
            package_name=package_name,
            old_version=old_version,
            new_version=new_version,
            ecosystem=PackageEcosystem.NPM,
            change_type=change_type,
            is_major_change=is_major
        ))
    
    return changes


def parse_requirements_txt_diff(diff_content: str) -> List[VersionChange]:
    """
    Parse requirements.txt diff to extract version changes.
    
    Args:
        diff_content: The diff content for requirements.txt
        
    Returns:
        List of version changes detected
    """
    changes: List[VersionChange] = []
    
    removed_packages: Dict[str, str] = {}
    added_packages: Dict[str, str] = {}
    
    # Pattern to match requirements.txt entries
    # Handles: package==1.0.0, package>=1.0.0, package~=1.0.0, package[extra]==1.0.0
    req_pattern = re.compile(r"^([a-zA-Z0-9_-]+)(?:\[[^\]]+\])?(?:([=<>!~]+)(.+))?$")
    
    for line in diff_content.split("\n"):
        if not line.startswith(("-", "+")) or line.startswith(("---", "+++")):
            continue
        
        # Remove the diff prefix for pattern matching
        content = line[1:].strip()
        
        # Skip comments and empty lines
        if not content or content.startswith("#"):
            continue
        
        match = req_pattern.match(content)
        if not match:
            continue
        
        package_name = match.group(1).lower()
        version = match.group(3) or ""
        
        if line.startswith("-") and not line.startswith("---"):
            removed_packages[package_name] = version
        elif line.startswith("+") and not line.startswith("+++"):
            added_packages[package_name] = version
    
    # Process the changes
    all_packages = set(removed_packages.keys()) | set(added_packages.keys())
    
    for package_name in all_packages:
        old_version = removed_packages.get(package_name)
        new_version = added_packages.get(package_name)
        
        change_type = _determine_change_type(old_version, new_version)
        
        if change_type == "unchanged":
            continue
        
        is_major = _is_major_version_change(old_version or "", new_version or "")
        
        changes.append(VersionChange(
            package_name=package_name,
            old_version=old_version,
            new_version=new_version,
            ecosystem=PackageEcosystem.PYTHON,
            change_type=change_type,
            is_major_change=is_major
        ))
    
    return changes


def parse_pyproject_toml_diff(diff_content: str) -> List[VersionChange]:
    """
    Parse pyproject.toml diff to extract version changes.
    
    Args:
        diff_content: The diff content for pyproject.toml
        
    Returns:
        List of version changes detected
    """
    changes: List[VersionChange] = []
    
    removed_packages: Dict[str, str] = {}
    added_packages: Dict[str, str] = {}
    
    # Pattern to match pyproject.toml dependency entries
    # Handles: "package>=1.0.0", "package==1.0.0", package = "^1.0.0"
    patterns = [
        re.compile(r'"([a-zA-Z0-9_-]+)(?:\[[^\]]+\])?([=<>!~]+)([^"]+)"'),  # "package>=1.0.0"
        re.compile(r"'([a-zA-Z0-9_-]+)(?:\[[^\]]+\])?([=<>!~]+)([^']+)'"),  # 'package>=1.0.0'
        re.compile(r'([a-zA-Z0-9_-]+)\s*=\s*"([^"]+)"'),  # package = "^1.0.0"
    ]
    
    for line in diff_content.split("\n"):
        if not line.startswith(("-", "+")) or line.startswith(("---", "+++")):
            continue
        
        content = line[1:].strip()
        
        for pattern in patterns:
            match = pattern.search(content)
            if match:
                groups = match.groups()
                package_name = groups[0].lower()
                version = groups[-1] if len(groups) > 1 else ""
                
                if line.startswith("-") and not line.startswith("---"):
                    removed_packages[package_name] = version
                elif line.startswith("+") and not line.startswith("+++"):
                    added_packages[package_name] = version
                break
    
    # Process the changes
    all_packages = set(removed_packages.keys()) | set(added_packages.keys())
    
    for package_name in all_packages:
        old_version = removed_packages.get(package_name)
        new_version = added_packages.get(package_name)
        
        change_type = _determine_change_type(old_version, new_version)
        
        if change_type == "unchanged":
            continue
        
        is_major = _is_major_version_change(old_version or "", new_version or "")
        
        changes.append(VersionChange(
            package_name=package_name,
            old_version=old_version,
            new_version=new_version,
            ecosystem=PackageEcosystem.PYTHON,
            change_type=change_type,
            is_major_change=is_major
        ))
    
    return changes


def detect_new_imports_js(diff_content: str, file_path: str) -> List[NewImport]:
    """
    Detect new imports added in JavaScript/TypeScript files.
    
    Args:
        diff_content: The diff content
        file_path: Path to the file being analyzed
        
    Returns:
        List of new imports detected
    """
    imports: List[NewImport] = []
    
    # Patterns for JS/TS imports
    import_patterns = [
        # import x from 'package'
        re.compile(r"^\+.*import\s+.*from\s+['\"]([^'\"./][^'\"]*)['\"]"),
        # import 'package'
        re.compile(r"^\+.*import\s+['\"]([^'\"./][^'\"]*)['\"]"),
        # require('package')
        re.compile(r"^\+.*require\s*\(\s*['\"]([^'\"./][^'\"]*)['\"]"),
        # dynamic import('package')
        re.compile(r"^\+.*import\s*\(\s*['\"]([^'\"./][^'\"]*)['\"]"),
    ]
    
    for line in diff_content.split("\n"):
        if not line.startswith("+") or line.startswith("+++"):
            continue
        
        for pattern in import_patterns:
            match = pattern.match(line)
            if match:
                import_path = match.group(1)
                # Extract package name (handle scoped packages)
                if import_path.startswith("@"):
                    parts = import_path.split("/")
                    package_name = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
                else:
                    package_name = import_path.split("/")[0]
                
                imports.append(NewImport(
                    import_path=package_name,
                    file_path=file_path,
                    ecosystem=PackageEcosystem.NPM,
                    is_external=True
                ))
                break
    
    return imports


def detect_new_imports_python(diff_content: str, file_path: str) -> List[NewImport]:
    """
    Detect new imports added in Python files.
    
    Args:
        diff_content: The diff content
        file_path: Path to the file being analyzed
        
    Returns:
        List of new imports detected
    """
    imports: List[NewImport] = []
    
    # Standard library modules to ignore
    stdlib_modules = {
        'os', 'sys', 're', 'json', 'datetime', 'time', 'math', 'random',
        'collections', 'itertools', 'functools', 'operator', 'typing',
        'pathlib', 'io', 'abc', 'copy', 'enum', 'dataclasses', 'contextlib',
        'logging', 'warnings', 'unittest', 'argparse', 'configparser',
        'hashlib', 'hmac', 'secrets', 'base64', 'uuid', 'asyncio',
        'concurrent', 'threading', 'multiprocessing', 'subprocess',
        'socket', 'http', 'urllib', 'email', 'html', 'xml',
        '__future__', 'builtins', 'types', 'inspect', 'dis', 'traceback',
        'pickle', 'shelve', 'sqlite3', 'csv', 'tempfile', 'shutil', 'glob',
        'fnmatch', 'stat', 'filecmp', 'difflib', 'textwrap', 'string',
        'struct', 'codecs', 'unicodedata', 'locale', 'gettext',
    }
    
    # Patterns for Python imports
    import_patterns = [
        # import package
        re.compile(r"^\+\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*)"),
        # from package import ...
        re.compile(r"^\+\s*from\s+([a-zA-Z_][a-zA-Z0-9_]*)"),
    ]
    
    for line in diff_content.split("\n"):
        if not line.startswith("+") or line.startswith("+++"):
            continue
        
        for pattern in import_patterns:
            match = pattern.match(line)
            if match:
                package_name = match.group(1)
                
                # Skip standard library and relative imports
                if package_name in stdlib_modules:
                    continue
                if package_name.startswith("_"):
                    continue
                
                imports.append(NewImport(
                    import_path=package_name,
                    file_path=file_path,
                    ecosystem=PackageEcosystem.PYTHON,
                    is_external=True
                ))
                break
    
    return imports


def analyze_diff_for_packages(
    diff_content: str,
    file_path: str
) -> PackageIntelligenceResult:
    """
    Analyze a diff for package changes and new imports.
    
    Args:
        diff_content: The diff content
        file_path: Path to the file
        
    Returns:
        PackageIntelligenceResult with detected changes
    """
    result = PackageIntelligenceResult(files_analyzed=[file_path])
    
    # Determine file type and process accordingly
    if file_path.endswith("package.json"):
        result.version_changes = parse_package_json_diff(diff_content)
        
    elif file_path.endswith("requirements.txt") or file_path.endswith("requirements-dev.txt"):
        result.version_changes = parse_requirements_txt_diff(diff_content)
        
    elif file_path.endswith("pyproject.toml"):
        result.version_changes = parse_pyproject_toml_diff(diff_content)
        
    elif file_path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
        result.new_imports = detect_new_imports_js(diff_content, file_path)
        
    elif file_path.endswith(".py"):
        result.new_imports = detect_new_imports_python(diff_content, file_path)
    
    return result


def build_package_context(
    version_changes: List[VersionChange],
    new_imports: List[NewImport]
) -> str:
    """
    Build a context string about package changes for the review agent.
    
    This creates a summary of all package changes that should inform
    the code review, including notes about major version changes.
    
    Args:
        version_changes: List of version changes detected
        new_imports: List of new imports detected
        
    Returns:
        A context string for the review agent
    """
    if not version_changes and not new_imports:
        return ""
    
    sections: List[str] = []
    sections.append("## Package Intelligence Report\n")
    
    # Process version changes
    major_changes: List[VersionChange] = []
    other_changes: List[VersionChange] = []
    
    if version_changes:
        sections.append("### Dependency Version Changes\n")
        
        major_changes = [v for v in version_changes if v.is_major_change]
        other_changes = [v for v in version_changes if not v.is_major_change]
        
        if major_changes:
            sections.append("**MAJOR VERSION CHANGES (Potential Breaking Changes):**")
            for change in major_changes:
                sections.append(
                    f"- `{change.package_name}`: {change.old_version or 'N/A'} -> {change.new_version or 'removed'} "
                    f"({change.ecosystem.value})"
                )
            sections.append("")
        
        if other_changes:
            sections.append("**Other Changes:**")
            for change in other_changes:
                symbol = {"added": "+", "removed": "-", "upgraded": "^", "downgraded": "v"}.get(change.change_type, "~")
                sections.append(
                    f"- [{symbol}] `{change.package_name}`: {change.old_version or 'N/A'} -> {change.new_version or 'removed'}"
                )
            sections.append("")
    
    # Process new imports
    if new_imports:
        sections.append("### New External Imports Detected\n")
        
        # Group by package
        imports_by_package: Dict[str, List[str]] = {}
        for imp in new_imports:
            if imp.import_path not in imports_by_package:
                imports_by_package[imp.import_path] = []
            imports_by_package[imp.import_path].append(imp.file_path)
        
        for package, files in imports_by_package.items():
            sections.append(f"- `{package}` (used in: {', '.join(files)})")
        sections.append("")
    
    # Add guidance
    sections.append("### Review Guidance\n")
    if major_changes:
        sections.append(
            "- **IMPORTANT**: Major version changes detected. Check for breaking changes and required migrations."
        )
        sections.append(
            "- Use `search_package_breaking_changes` tool to find migration guides if needed."
        )
    
    sections.append(
        "- Verify that any new imports are intentional and necessary."
    )
    sections.append(
        "- Check that deprecated APIs from updated packages are not being used."
    )
    
    return "\n".join(sections)


# =============================================================================
# LangChain Tools
# =============================================================================

@tool
def analyze_package_changes(
    diff_content: str,
    file_path: str
) -> str:
    """
    Analyze a diff for package version changes and new imports.
    
    Use this tool when reviewing PRs that modify package.json, requirements.txt,
    pyproject.toml, or add new imports to source files. It will detect:
    - Version upgrades/downgrades
    - New dependencies added
    - Dependencies removed
    - New imports in source files
    
    Args:
        diff_content: The raw diff content for the file
        file_path: Path to the file being analyzed (e.g., 'package.json', 'src/app.ts', 'requirements.txt')
    
    Returns:
        JSON string with detected changes
    """
    result = analyze_diff_for_packages(diff_content, file_path)
    return json.dumps(result.to_dict(), indent=2)


@tool
def get_package_upgrade_context(
    package_name: str,
    old_version: str,
    new_version: str,
    ecosystem: str = "npm"
) -> str:
    """
    Get comprehensive context about a package upgrade for code review.
    
    This tool searches for breaking changes, deprecations, and new APIs
    for a package upgrade, providing context to inform the code review.
    
    Args:
        package_name: Name of the package being upgraded
        old_version: The version being upgraded from
        new_version: The version being upgraded to
        ecosystem: 'npm' for JavaScript/TypeScript, 'python' for Python/pip
    
    Returns:
        Comprehensive context about the package upgrade
    """
    if not is_search_enabled():
        return f"Web search disabled. Unable to get context for {package_name} upgrade."
    
    sections: List[str] = []
    sections.append(f"# Package Upgrade Context: {package_name}")
    sections.append(f"**{old_version} -> {new_version}** ({ecosystem})\n")
    
    # Check if this is a major version change
    is_major = _is_major_version_change(old_version, new_version)
    
    if is_major:
        sections.append("**WARNING: This is a MAJOR version change. Breaking changes are likely.**\n")
    
    # Search for breaking changes
    sections.append("## Breaking Changes")
    if ecosystem == "python":
        breaking_info = search_python_package_changes.invoke({
            "package_name": package_name,
            "from_version": old_version,
            "to_version": new_version
        })
    else:
        breaking_info = search_package_breaking_changes.invoke({
            "package_name": package_name,
            "from_version": old_version,
            "to_version": new_version,
            "ecosystem": ecosystem
        })
    sections.append(breaking_info)
    
    # Search for deprecations in the new version
    sections.append("\n## Deprecated APIs")
    deprecation_info = search_package_deprecations.invoke({
        "package_name": package_name,
        "version": new_version,
        "ecosystem": ecosystem
    })
    sections.append(deprecation_info)
    
    # Search for new APIs
    sections.append("\n## New APIs and Features")
    new_api_info = search_new_package_apis.invoke({
        "package_name": package_name,
        "version": new_version,
        "ecosystem": ecosystem
    })
    sections.append(new_api_info)
    
    return "\n".join(sections)


def get_all_package_intelligence_tools() -> List:
    """Return all package intelligence tools for agent registration."""
    return [
        analyze_package_changes,
        get_package_upgrade_context,
    ]
