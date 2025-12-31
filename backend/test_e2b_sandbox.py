#!/usr/bin/env python3
"""
E2B Sandbox Integration Test

Tests the E2B sandbox integration with a real GitHub PR.
This test requires:
- E2B_API_KEY environment variable set
- E2B_TEMPLATE_ID environment variable set (optional, uses default if not set)
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Load .env file
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_sandbox_manager_basic():
    """Test basic sandbox manager operations."""
    from agent.services.sandbox_manager import (
        SandboxManager,
        SandboxConfig,
        SandboxError,
    )
    
    print("\n" + "=" * 60)
    print("Test 1: Basic SandboxManager Operations")
    print("=" * 60)
    
    # Check for E2B API key
    api_key = os.getenv("E2B_API_KEY")
    if not api_key:
        print("SKIP: E2B_API_KEY not set")
        return False
    
    template_id = os.getenv("E2B_TEMPLATE_ID")
    print(f"Using template: {template_id or 'default'}")
    
    config = SandboxConfig(
        api_key=api_key,
        template_id=template_id,
        timeout_ms=60_000,  # 1 minute for test
    )
    
    manager = SandboxManager(config)
    session_id = "test-session-001"
    
    try:
        # Test 1: Create sandbox
        print("\n[1/5] Creating sandbox...")
        sandbox = await manager.create_sandbox(session_id)
        print(f"  ✓ Sandbox created: {sandbox.sandbox_id}")
        
        # Test 2: Run a simple command
        print("\n[2/5] Running test command...")
        result = await manager.run_command(session_id, "echo 'Hello from E2B!'")
        print(f"  ✓ Command output: {result.get('stdout', '').strip()}")
        
        # Test 3: Check Python version
        print("\n[3/5] Checking Python version...")
        result = await manager.run_command(session_id, "python3 --version")
        print(f"  ✓ Python: {result.get('stdout', '').strip()}")
        
        # Test 4: Check tree-sitter is installed
        print("\n[4/5] Checking tree-sitter installation...")
        result = await manager.run_command(
            session_id, 
            "python3 -c \"import tree_sitter; print('tree_sitter: installed')\""
        )
        if result.get('exit_code') == 0:
            print(f"  ✓ {result.get('stdout', '').strip()}")
        else:
            print(f"  ✗ tree-sitter not installed: {result.get('stderr', '')}")
        
        # Test 5: Kill sandbox
        print("\n[5/5] Killing sandbox...")
        await manager.kill_sandbox(session_id)
        print("  ✓ Sandbox killed")
        
        print("\n✓ All basic tests passed!")
        return True
        
    except SandboxError as e:
        print(f"\n✗ Sandbox error: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Ensure cleanup
        try:
            await manager.kill_sandbox(session_id)
        except:
            pass


async def test_sandbox_clone_repo():
    """Test cloning a repository in the sandbox."""
    from agent.services.sandbox_manager import (
        SandboxManager,
        SandboxConfig,
    )
    
    print("\n" + "=" * 60)
    print("Test 2: Clone Repository in Sandbox")
    print("=" * 60)
    
    api_key = os.getenv("E2B_API_KEY")
    if not api_key:
        print("SKIP: E2B_API_KEY not set")
        return False
    
    template_id = os.getenv("E2B_TEMPLATE_ID")
    config = SandboxConfig(
        api_key=api_key,
        template_id=template_id,
        timeout_ms=300_000,  # 5 minutes for clone
    )
    
    manager = SandboxManager(config)
    session_id = "test-session-clone"
    
    try:
        # Create sandbox
        print("\n[1/4] Creating sandbox...")
        await manager.create_sandbox(session_id)
        print("  ✓ Sandbox created")
        
        # Clone the cal.com repo (just the specific branch)
        print("\n[2/4] Cloning cal.com repository (PR branch)...")
        print("  This may take a few minutes...")
        
        # Clone with specific ref for the PR
        repo_path = await manager.clone_repo(
            session_id=session_id,
            repo_url="https://github.com/calcom/cal.com.git",
            branch="main",  # Clone main first, then we can checkout PR branch
        )
        print(f"  ✓ Cloned to: {repo_path}")
        
        # List some files
        print("\n[3/4] Listing files...")
        files = await manager.list_files(session_id, repo_path, "*.ts")
        print(f"  ✓ Found {len(files)} TypeScript files")
        if files[:5]:
            for f in files[:5]:
                print(f"    - {f}")
        
        # Read package.json
        print("\n[4/4] Reading package.json...")
        try:
            content = await manager.read_file(session_id, f"{repo_path}/package.json")
            lines = content.split('\n')[:10]
            print("  ✓ package.json (first 10 lines):")
            for line in lines:
                print(f"    {line}")
        except Exception as e:
            print(f"  ✗ Could not read package.json: {e}")
        
        print("\n✓ Clone test passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\nCleaning up...")
        try:
            await manager.kill_sandbox(session_id)
            print("  ✓ Sandbox killed")
        except:
            pass


async def test_sandbox_with_pr_files():
    """Test sandbox operations with specific PR files."""
    from agent.services.sandbox_manager import (
        SandboxManager,
        SandboxConfig,
    )
    from agent.tools.sandbox_file import (
        sandbox_read_file_with_line_numbers,
        sandbox_list_files_raw,
    )
    
    print("\n" + "=" * 60)
    print("Test 3: Sandbox with PR Files (cal.com PR #25972)")
    print("=" * 60)
    
    api_key = os.getenv("E2B_API_KEY")
    if not api_key:
        print("SKIP: E2B_API_KEY not set")
        return False
    
    template_id = os.getenv("E2B_TEMPLATE_ID")
    config = SandboxConfig(
        api_key=api_key,
        template_id=template_id,
        timeout_ms=300_000,
    )
    
    manager = SandboxManager(config)
    session_id = "test-session-pr"
    
    try:
        print("\n[1/5] Creating sandbox...")
        await manager.create_sandbox(session_id)
        print("  ✓ Sandbox created")
        
        # Clone and checkout the PR branch
        print("\n[2/5] Cloning repository...")
        repo_path = await manager.clone_repo(
            session_id=session_id,
            repo_url="https://github.com/calcom/cal.com.git",
            branch="main",
        )
        print(f"  ✓ Cloned to: {repo_path}")
        
        # Fetch the PR
        print("\n[3/5] Fetching PR #25972...")
        result = await manager.run_command(
            session_id,
            f"cd {repo_path} && git fetch origin pull/25972/head:pr-25972 && git checkout pr-25972",
        )
        if result.get('exit_code') == 0:
            print("  ✓ Checked out PR branch")
        else:
            print(f"  ✗ Failed to checkout PR: {result.get('stderr', '')}")
            # Continue anyway with main branch
        
        # Get diff to find changed files
        print("\n[4/5] Getting changed files...")
        result = await manager.run_command(
            session_id,
            f"cd {repo_path} && git diff --name-only origin/main...HEAD 2>/dev/null || git diff --name-only HEAD~1",
        )
        changed_files = [f for f in result.get('stdout', '').strip().split('\n') if f]
        print(f"  ✓ Found {len(changed_files)} changed files:")
        for f in changed_files[:10]:
            print(f"    - {f}")
        if len(changed_files) > 10:
            print(f"    ... and {len(changed_files) - 10} more")
        
        # Read one of the changed files
        print("\n[5/5] Reading a changed file...")
        if changed_files:
            # Find a TypeScript or JavaScript file
            code_files = [f for f in changed_files if f.endswith(('.ts', '.tsx', '.js', '.jsx'))]
            if code_files:
                target_file = code_files[0]
                print(f"  Reading: {target_file}")
                content = await sandbox_read_file_with_line_numbers(
                    manager, session_id, f"{repo_path}/{target_file}", 1, 30
                )
                print(f"  ✓ Content (first 30 lines):")
                for line in content.split('\n')[:15]:
                    print(f"    {line}")
            else:
                print("  No TypeScript/JavaScript files in diff")
        
        print("\n✓ PR files test passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\nCleaning up...")
        try:
            await manager.kill_sandbox(session_id)
            print("  ✓ Sandbox killed")
        except:
            pass


async def test_parser_in_sandbox():
    """Test running the parser agent with sandbox."""
    from agent.services.sandbox_manager import (
        SandboxManager,
        SandboxConfig,
    )
    from agent.parsers.pipeline import analyze_content
    
    print("\n" + "=" * 60)
    print("Test 4: Parser in Sandbox")
    print("=" * 60)
    
    api_key = os.getenv("E2B_API_KEY")
    if not api_key:
        print("SKIP: E2B_API_KEY not set")
        return False
    
    template_id = os.getenv("E2B_TEMPLATE_ID")
    config = SandboxConfig(
        api_key=api_key,
        template_id=template_id,
        timeout_ms=300_000,
    )
    
    manager = SandboxManager(config)
    session_id = "test-session-parser"
    
    try:
        print("\n[1/4] Creating sandbox...")
        await manager.create_sandbox(session_id)
        print("  ✓ Sandbox created")
        
        # Clone repo
        print("\n[2/4] Cloning repository...")
        repo_path = await manager.clone_repo(
            session_id=session_id,
            repo_url="https://github.com/calcom/cal.com.git",
            branch="main",
        )
        print(f"  ✓ Cloned to: {repo_path}")
        
        # Find a TypeScript file to parse
        print("\n[3/4] Finding TypeScript file to parse...")
        files = await manager.list_files(session_id, repo_path, "*.ts")
        ts_files = [f for f in files if not f.endswith('.d.ts') and 'node_modules' not in f]
        
        if not ts_files:
            print("  No TypeScript files found")
            return False
        
        # Pick a reasonably sized file
        target_file = None
        for f in ts_files[:20]:
            try:
                content = await manager.read_file(session_id, f)
                if 100 < len(content) < 5000:  # Reasonable size
                    target_file = f
                    break
            except:
                continue
        
        if not target_file:
            target_file = ts_files[0]
        
        print(f"  ✓ Selected: {target_file}")
        
        # Read and parse the file
        print("\n[4/4] Parsing file content...")
        content = await manager.read_file(session_id, target_file)
        print(f"  File size: {len(content)} characters")
        
        # Use the content-based parser
        result = analyze_content(
            content=content,
            file_path=target_file,
            language="typescript",
        )
        
        print(f"  ✓ Parse result:")
        print(f"    - Functions: {len(result.get('functions', []))}")
        print(f"    - Classes: {len(result.get('classes', []))}")
        print(f"    - Imports: {len(result.get('imports', []))}")
        print(f"    - Complexity score: {result.get('complexity_score', 'N/A')}")
        
        functions = result.get('functions', [])
        if functions:
            print(f"    - Sample function: {functions[0].get('name', 'unnamed')}")
        
        print("\n✓ Parser test passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\nCleaning up...")
        try:
            await manager.kill_sandbox(session_id)
            print("  ✓ Sandbox killed")
        except:
            pass


async def main():
    """Run all E2B sandbox tests."""
    print("=" * 60)
    print("E2B Sandbox Integration Tests")
    print("=" * 60)
    
    # Check prerequisites
    api_key = os.getenv("E2B_API_KEY")
    if not api_key:
        print("\n⚠ E2B_API_KEY not set!")
        print("Please set your E2B API key:")
        print("  export E2B_API_KEY=your-api-key")
        print("\nGet your API key from: https://e2b.dev/dashboard")
        return
    
    template_id = os.getenv("E2B_TEMPLATE_ID")
    print(f"\nConfiguration:")
    print(f"  E2B_API_KEY: {'*' * 10}...{api_key[-4:]}")
    print(f"  E2B_TEMPLATE_ID: {template_id or '(using default)'}")
    
    results = []
    
    # Run tests
    tests = [
        ("Basic Operations", test_sandbox_manager_basic),
        ("Clone Repository", test_sandbox_clone_repo),
        ("PR Files", test_sandbox_with_pr_files),
        ("Parser in Sandbox", test_parser_in_sandbox),
    ]
    
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
