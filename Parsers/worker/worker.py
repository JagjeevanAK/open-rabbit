"""
Celery Worker Tasks
Handles asynchronous pipeline and workflow execution
"""

import os
import json
from pathlib import Path
from typing import Dict, Any
from celery import Celery, chain
from celery.utils.log import get_task_logger

# Import pipeline and workflow
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import AnalysisPipeline
from workflow import app as workflow_app
from workflow import AgentState

# Initialize Celery app
app = Celery(
    "Parsers-Worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
)

logger = get_task_logger(__name__)


@app.task(name="worker.run_pipeline", bind=True)
def run_pipeline(self, file_path: str, output_dir: str = "output") -> Dict[str, Any]:
    """
    Task 1: Run the analysis pipeline on a file
    
    This task:
    1. Takes a file path as input
    2. Runs the complete AST -> CFG -> PDG pipeline
    3. Exports results to the output directory
    4. Returns metadata about the generated files
    
    Args:
        file_path: Path to the source file to analyze
        output_dir: Directory to save output files (default: "output")
    
    Returns:
        Dictionary containing:
        - status: Success/failure status
        - file_path: Input file path
        - output_dir: Output directory path
        - files_generated: List of generated files
        - language: Detected language
        - summary: Brief summary of analysis
    """
    try:
        logger.info(f"Starting pipeline analysis for file: {file_path}")
        self.update_state(state='PROCESSING', meta={'step': 'initializing'})
        
        # Validate input file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path}")
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize pipeline (language auto-detection)
        logger.info("Initializing analysis pipeline...")
        self.update_state(state='PROCESSING', meta={'step': 'parsing'})
        pipeline = AnalysisPipeline()
        
        # Run full pipeline
        logger.info("Running AST -> CFG -> PDG pipeline...")
        pipeline.run_pipeline_on_file(file_path)
        
        # Export results
        logger.info("Exporting results...")
        self.update_state(state='PROCESSING', meta={'step': 'exporting'})
        
        # Export JSON analysis
        analysis_json_path = output_path / "analysis.json"
        pipeline.export_to_json(str(analysis_json_path))
        
        # Export DOT visualizations
        pipeline.export_visualizations(output_dir)
        
        # Export detailed PDG JSON
        if pipeline.pdg:
            detailed_pdg_path = output_path / "detailed_pdg.json"
            pdg_dict = pipeline.pdg.to_dict()
            with open(detailed_pdg_path, 'w', encoding='utf-8') as f:
                json.dump(pdg_dict, f, indent=2)
            logger.info(f"Detailed PDG saved to {detailed_pdg_path}")
        
        # Collect generated files
        files_generated = []
        for file in output_path.iterdir():
            if file.is_file():
                files_generated.append(str(file))
        
        # Create summary
        summary = {
            "language": pipeline.language,
            "ast_parsed": pipeline.ast_tree is not None,
            "cfg_built": pipeline.cfg is not None,
            "pdg_built": pipeline.pdg is not None,
        }
        
        if pipeline.cfg:
            summary["cfg_blocks"] = len(pipeline.cfg.blocks)
        
        if pipeline.pdg:
            summary["pdg_nodes"] = len(pipeline.pdg.nodes)
            summary["pdg_variables"] = len(pipeline.pdg.variables)
        
        logger.info(f"Pipeline completed successfully. Generated {len(files_generated)} files.")
        
        return {
            "status": "success",
            "file_path": file_path,
            "output_dir": str(output_path.absolute()),
            "files_generated": files_generated,
            "language": pipeline.language,
            "summary": summary,
        }
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "file_path": file_path,
            "error": str(e),
            "error_type": type(e).__name__,
        }


@app.task(name="worker.run_workflow", bind=True)
def run_workflow(self, pipeline_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task 2: Run the workflow analysis on pipeline output
    
    This task:
    1. Takes the pipeline result as input
    2. Loads analysis.json and detailed_pdg.json from output directory
    3. Runs the LangGraph workflow for code review
    4. Returns the workflow analysis results
    
    Args:
        pipeline_result: Result from run_pipeline task
    
    Returns:
        Dictionary containing:
        - status: Success/failure status
        - pipeline_status: Status from previous pipeline task
        - output_dir: Output directory used
        - analysis_summary: AST analysis summary
        - pdg_summary: PDG analysis summary
        - review_output: Final code review output
    """
    try:
        logger.info("Starting workflow analysis...")
        self.update_state(state='PROCESSING', meta={'step': 'loading_data'})
        
        # Check pipeline status
        if pipeline_result.get("status") != "success":
            logger.error("Pipeline task failed, cannot run workflow")
            return {
                "status": "error",
                "error": "Pipeline task failed",
                "pipeline_result": pipeline_result,
            }
        
        output_dir = pipeline_result.get("output_dir")
        if not output_dir:
            raise ValueError("No output_dir in pipeline result")
        
        # Verify required files exist
        analysis_json = os.path.join(output_dir, "analysis.json")
        pdg_json = os.path.join(output_dir, "detailed_pdg.json")
        
        if not os.path.exists(analysis_json):
            raise FileNotFoundError(f"analysis.json not found in {output_dir}")
        if not os.path.exists(pdg_json):
            raise FileNotFoundError(f"detailed_pdg.json not found in {output_dir}")
        
        logger.info(f"Loading data from {output_dir}")
        self.update_state(state='PROCESSING', meta={'step': 'running_workflow'})
        
        # Run the workflow
        logger.info("Executing LangGraph workflow...")
        initial_state: AgentState = {"messages": []}
        result = workflow_app.invoke(initial_state)
        
        # Extract results
        messages = result.get("messages", [])
        analysis_summary = result.get("analysis_summary", "N/A")
        pdg_summary = result.get("pdg_summary", "N/A")
        
        # Get final review output
        review_output = ""
        if messages:
            last_message = messages[-1]
            review_output = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        logger.info("Workflow completed successfully")
        
        return {
            "status": "success",
            "pipeline_status": pipeline_result.get("status"),
            "output_dir": output_dir,
            "file_analyzed": pipeline_result.get("file_path"),
            "language": pipeline_result.get("language"),
            "analysis_summary": analysis_summary,
            "pdg_summary": pdg_summary,
            "review_output": review_output,
        }
        
    except Exception as e:
        logger.error(f"Workflow failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "pipeline_result": pipeline_result,
        }


@app.task(name="worker.process_file")
def process_file(file_path: str, output_dir: str = "output") -> str:
    """
    Main task: Process a file through pipeline and workflow
    
    This is a convenience task that chains:
    1. run_pipeline - Analyze the file
    2. run_workflow - Review the analysis
    
    Args:
        file_path: Path to the source file
        output_dir: Output directory for results
    
    Returns:
        Task ID for tracking the chained tasks
    """
    logger.info(f"Creating processing chain for file: {file_path}")
    
    # Create task chain: pipeline -> workflow
    task_chain = chain(
        run_pipeline.s(file_path, output_dir),
        run_workflow.s()
    )
    
    # Execute the chain
    result = task_chain.apply_async()
    
    return result.id


if __name__ == "__main__":
    # Run worker with: celery -A worker.worker worker --loglevel=info
    app.start()

