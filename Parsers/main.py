"""
Main Entry Point
Demonstrates how to use the Celery-based pipeline and workflow system
"""

import sys
import argparse
from pathlib import Path
from client.client import (
    submit_file_for_processing,
    submit_pipeline_only,
    get_task_status,
    wait_for_task,
    revoke_task
)


def process_file_async(file_path: str, output_dir: str = "output", wait: bool = True):
    """
    Process a file asynchronously through pipeline and workflow
    
    Args:
        file_path: Path to source file
        output_dir: Output directory for results
        wait: If True, wait for completion and print results
    """
    print(f"Processing file: {file_path}")
    print(f"Output directory: {output_dir}")
    print("-" * 60)
    
    # Submit task
    task_id = submit_file_for_processing(file_path, output_dir)
    
    if wait:
        # Wait for completion of the chain task
        result = wait_for_task(task_id, timeout=600, poll_interval=3)
        
        # Print results
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        
        # Handle chained task result - it returns the final task ID
        if isinstance(result, str):
            # Result is a task ID, get the actual workflow result
            print(f"\nChained task ID: {result}")
            print("Fetching workflow results...")
            workflow_result = wait_for_task(result, timeout=600, poll_interval=3)
            
            if isinstance(workflow_result, dict) and workflow_result.get("status") == "success":
                print(f"\n✓ File analyzed: {workflow_result.get('file_analyzed')}")
                print(f"✓ Language: {workflow_result.get('language')}")
                print(f"✓ Output directory: {workflow_result.get('output_dir')}")
                
                print("\n--- AST Analysis Summary ---")
                print(workflow_result.get("analysis_summary", "N/A"))
                
                print("\n--- PDG Analysis Summary ---")
                print(workflow_result.get("pdg_summary", "N/A"))
                
                print("\n--- Code Review Output ---")
                print(workflow_result.get("review_output", "N/A"))
            else:
                print(f"\n✗ Workflow failed: {workflow_result}")
        elif isinstance(result, dict):
            # Direct result dict
            if result.get("status") == "success":
                print(f"\n✓ File analyzed: {result.get('file_analyzed')}")
                print(f"✓ Language: {result.get('language')}")
                print(f"✓ Output directory: {result.get('output_dir')}")
                
                print("\n--- AST Analysis Summary ---")
                print(result.get("analysis_summary", "N/A"))
                
                print("\n--- PDG Analysis Summary ---")
                print(result.get("pdg_summary", "N/A"))
                
                print("\n--- Code Review Output ---")
                print(result.get("review_output", "N/A"))
            else:
                print(f"\n✗ Task failed: {result.get('error', 'Unknown error')}")
        else:
            print(f"\n✗ Unexpected result type: {type(result)}")
            print(f"Result: {result}")
        
        print("\n" + "=" * 60)
    else:
        print(f"\nTask submitted with ID: {task_id}")
        print("Use the check-status command to monitor progress:")
        print(f"  python main.py check-status {task_id}")


def process_pipeline_only(file_path: str, output_dir: str = "output", wait: bool = True):
    """
    Process a file through pipeline only (no workflow)
    
    Args:
        file_path: Path to source file
        output_dir: Output directory for results
        wait: If True, wait for completion and print results
    """
    print(f"Running pipeline only for: {file_path}")
    print(f"Output directory: {output_dir}")
    print("-" * 60)
    
    # Submit task
    task_id = submit_pipeline_only(file_path, output_dir)
    
    if wait:
        # Wait for completion
        result = wait_for_task(task_id, timeout=600, poll_interval=3)
        
        # Print results
        print("\n" + "=" * 60)
        print("PIPELINE RESULTS")
        print("=" * 60)
        
        if result.get("status") == "success":
            print(f"\n✓ File: {result.get('file_path')}")
            print(f"✓ Language: {result.get('language')}")
            print(f"✓ Output directory: {result.get('output_dir')}")
            print(f"✓ Files generated: {len(result.get('files_generated', []))}")
            
            print("\nGenerated files:")
            for file in result.get('files_generated', []):
                print(f"  - {file}")
            
            summary = result.get('summary', {})
            print("\nAnalysis Summary:")
            for key, value in summary.items():
                print(f"  {key}: {value}")
        else:
            print(f"\n✗ Pipeline failed: {result.get('error', 'Unknown error')}")
        
        print("\n" + "=" * 60)
    else:
        print(f"\nPipeline task submitted with ID: {task_id}")


def check_status(task_id: str):
    """Check the status of a task"""
    print(f"Checking status for task: {task_id}")
    print("-" * 60)
    
    status = get_task_status(task_id)
    
    print(f"State: {status['state']}")
    print(f"Ready: {status['ready']}")
    
    if status['ready']:
        print(f"Successful: {status['successful']}")
        
        if status['successful']:
            print("\nResult:")
            result = status['result']
            if isinstance(result, dict):
                for key, value in result.items():
                    if key in ['analysis_summary', 'pdg_summary', 'review_output']:
                        print(f"\n{key}:")
                        print(value)
                    else:
                        print(f"  {key}: {value}")
            else:
                print(result)
        else:
            print(f"\nError: {status['info']}")
    else:
        print(f"Progress: {status['info']}")


def cancel_task(task_id: str, terminate: bool = False):
    """Cancel a running task"""
    print(f"Canceling task: {task_id}")
    
    result = revoke_task(task_id, terminate)
    
    print(f"Status: {result['status']}")
    if terminate:
        print("Task terminated immediately")
    else:
        print("Task revoked (will not start if pending)")


def main():
    """Main entry point with CLI interface"""
    parser = argparse.ArgumentParser(
        description="Process source code files through AST/CFG/PDG pipeline and AI workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a Python file with full workflow
  python main.py process example.py

  # Process with custom output directory
  python main.py process src/app.js --output-dir ./results

  # Run pipeline only (no AI workflow)
  python main.py pipeline example.py

  # Submit task without waiting
  python main.py process example.py --no-wait

  # Check task status
  python main.py check-status <task-id>

  # Cancel a task
  python main.py cancel <task-id>

Before running, make sure:
  1. Redis is running: redis-server
  2. Celery worker is running: celery -A worker.worker worker --loglevel=info
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process file through pipeline and workflow')
    process_parser.add_argument('file', help='Path to source file to analyze')
    process_parser.add_argument('--output-dir', default='output', help='Output directory (default: output)')
    process_parser.add_argument('--no-wait', action='store_true', help='Submit task without waiting')
    
    # Pipeline command
    pipeline_parser = subparsers.add_parser('pipeline', help='Run pipeline only (no workflow)')
    pipeline_parser.add_argument('file', help='Path to source file to analyze')
    pipeline_parser.add_argument('--output-dir', default='output', help='Output directory (default: output)')
    pipeline_parser.add_argument('--no-wait', action='store_true', help='Submit task without waiting')
    
    # Check status command
    status_parser = subparsers.add_parser('check-status', help='Check task status')
    status_parser.add_argument('task_id', help='Task ID to check')
    
    # Cancel command
    cancel_parser = subparsers.add_parser('cancel', help='Cancel a task')
    cancel_parser.add_argument('task_id', help='Task ID to cancel')
    cancel_parser.add_argument('--terminate', action='store_true', help='Terminate immediately')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'process':
            process_file_async(args.file, args.output_dir, wait=not args.no_wait)
        
        elif args.command == 'pipeline':
            process_pipeline_only(args.file, args.output_dir, wait=not args.no_wait)
        
        elif args.command == 'check-status':
            check_status(args.task_id)
        
        elif args.command == 'cancel':
            cancel_task(args.task_id, args.terminate)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
