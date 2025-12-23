"""
Parsers - Code Analysis Pipeline

Entry point for AST and Semantic code analysis.
"""

import argparse
import sys
from pathlib import Path

from pipeline import AnalysisPipeline, analyze_file, analyze_code


def main():
    """Main entry point with CLI interface"""
    parser = argparse.ArgumentParser(
        description="Analyze source code using AST and Semantic analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a Python file
  python main.py analyze example.py

  # Analyze with custom output directory
  python main.py analyze src/app.js --output ./results

  # Analyze and print summary
  python main.py analyze example.py --summary
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze a source file')
    analyze_parser.add_argument('file', help='Path to source file')
    analyze_parser.add_argument('--output', '-o', default='output', help='Output directory (default: output)')
    analyze_parser.add_argument('--summary', '-s', action='store_true', help='Print analysis summary')
    analyze_parser.add_argument('--json', '-j', help='Export results to JSON file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'analyze':
            file_path = args.file
            
            if not Path(file_path).exists():
                print(f"Error: File not found: {file_path}")
                sys.exit(1)
            
            print(f"Analyzing: {file_path}")
            print("-" * 50)
            
            # Run analysis
            pipeline = AnalysisPipeline()
            results = pipeline.run_pipeline_on_file(file_path, output_dir=args.output)
            
            # Print summary if requested
            if args.summary:
                pipeline.print_summary()
            
            # Export to JSON if requested
            if args.json:
                pipeline.export_to_json(args.json)
            
            # Print generated files
            if results.get('report_paths'):
                print("\nGenerated reports:")
                for report_type, path in results['report_paths'].items():
                    print(f"  - {report_type}: {path}")
            
            print("\n✓ Analysis complete")
                
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
