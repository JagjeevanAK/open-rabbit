#!/usr/bin/env python3
"""
Test Parser Agent Integration

This script tests the integration between backend agent tools
and the Parsers Celery worker.
"""

import sys
import os
import json

# Add backend to path
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, backend_dir)

from agent.tools.Parsers import (
    parse_code_file,
    analyze_changed_files,
    get_parser_capabilities,
    CELERY_AVAILABLE
)


def test_capabilities():
    """Test 1: Check parser capabilities"""
    print("\n" + "=" * 70)
    print("TEST 1: Parser Capabilities")
    print("=" * 70 + "\n")
    
    result = get_parser_capabilities.invoke({})
    data = json.loads(result)
    
    print(f"Celery Available: {data['celery_available']}")
    print(f"Supported Languages: {', '.join(data['supported_languages'])}")
    print(f"\nAnalysis Capabilities:")
    for cap in data['analysis_capabilities']:
        print(f"  - {cap}")
    
    print(f"\nRequirements:")
    for req in data['requirements']:
        print(f"  - {req}")
    
    return data['celery_available']


def test_file_analysis():
    """Test 2: Analyze a sample file"""
    print("\n" + "=" * 70)
    print("TEST 2: File Analysis")
    print("=" * 70 + "\n")
    
    # Create a test file
    test_file = "/tmp/test_parser_integration.py"
    with open(test_file, 'w') as f:
        f.write("""
def calculate_sum(numbers):
    '''Calculate sum of positive numbers'''
    total = 0
    for num in numbers:
        if num > 0:
            total += num
    return total

def main():
    data = [1, -2, 3, 4, -5]
    result = calculate_sum(data)
    print(f"Sum: {result}")

if __name__ == "__main__":
    main()
""")
    
    print(f"Created test file: {test_file}")
    print(f"Submitting to Parsers agent...\n")
    
    if not CELERY_AVAILABLE:
        print("⚠️  Celery not available. Install with: uv add celery redis")
        print("    Also ensure Redis is running and Parsers worker is started.")
        return False
    
    try:
        # Test pipeline only (faster)
        result = parse_code_file.invoke({
            "file_path": test_file,
            "include_workflow": False  # Pipeline only for quick test
        })
        
        data = json.loads(result)
        
        if data.get("success"):
            print("✓ Analysis successful!")
            print(f"\nFile: {data['file_path']}")
            print(f"Language: {data['language']}")
            print(f"Output Dir: {data.get('output_dir', 'N/A')}")
            print(f"\nSummary:\n{data.get('summary', 'No summary')}")
            
            if data.get('files_generated'):
                print(f"\nGenerated files:")
                for f in data['files_generated']:
                    print(f"  - {f}")
            
            return True
        else:
            print(f"✗ Analysis failed: {data.get('error')}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_analysis():
    """Test 3: Analyze multiple files"""
    print("\n" + "=" * 70)
    print("TEST 3: Batch Analysis")
    print("=" * 70 + "\n")
    
    if not CELERY_AVAILABLE:
        print("⚠️  Celery not available. Skipping batch analysis test.")
        return False
    
    # Create test files
    files = []
    
    file1 = "/tmp/test_utils.py"
    with open(file1, 'w') as f:
        f.write("def add(a, b): return a + b\ndef sub(a, b): return a - b")
    files.append(file1)
    
    file2 = "/tmp/test_calculator.py"
    with open(file2, 'w') as f:
        f.write("class Calculator:\n    def multiply(self, a, b): return a * b")
    files.append(file2)
    
    print(f"Created {len(files)} test files")
    print(f"Submitting batch to Parsers agent...\n")
    
    try:
        result = analyze_changed_files.invoke({
            "file_paths": files
        })
        
        data = json.loads(result)
        
        if data.get("success"):
            print(f"✓ Batch analysis successful!")
            print(f"  Analyzed: {data['analyzed_files']} files")
            print(f"  Errors: {len(data.get('errors', []))}")
            return True
        else:
            print(f"✗ Batch analysis had errors:")
            for error in data.get('errors', []):
                print(f"  - {error['file_path']}: {error['error']}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("PARSER AGENT INTEGRATION TESTS")
    print("=" * 70)
    
    results = []
    
    # Test 1: Always runs
    celery_available = test_capabilities()
    results.append(("Capabilities Check", True))
    
    if not celery_available:
        print("\n" + "=" * 70)
        print("SETUP REQUIRED")
        print("=" * 70)
        print("\nTo run full tests, you need:")
        print("\n1. Install dependencies:")
        print("   cd backend && uv add celery redis")
        print("\n2. Start Redis:")
        print("   redis-server")
        print("\n3. Start Parsers worker:")
        print("   cd Parsers && celery -A worker.worker worker --loglevel=info")
        print("\n4. Run tests again:")
        print("   cd backend && uv run python agent/examples/test_parser_integration.py")
        print("\n" + "=" * 70)
        return 1
    
    # Test 2: File analysis
    results.append(("File Analysis", test_file_analysis()))
    
    # Test 3: Batch analysis
    results.append(("Batch Analysis", test_batch_analysis()))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n✅ All tests passed!")
        print("\nThe parser agent integration is working correctly.")
        print("You can now use these tools in your backend agent.")
        return 0
    else:
        print("\n❌ Some tests failed.")
        print("\nCheck the errors above and ensure:")
        print("  - Redis is running")
        print("  - Parsers Celery worker is running")
        print("  - File paths are accessible")
        return 1


if __name__ == "__main__":
    sys.exit(main())
