# FilePath: main.py
# -*- coding: utf-8 -*-
"""
DeepFlow project unified entry point.
Provides two startup modes:
1. API service mode: Starts the FastAPI server to provide full web services.
2. Command line mode: Directly runs a query in the terminal for quick testing and debugging.
"""
import argparse
import uvicorn
import asyncio
import logging # Added import for logging
from src.server.app import app # Import FastAPI instance
from src.graph.builder import graph # Import compiled LangGraph instance
from src.graph.types import State # Import graph state definition
from src.utils.logging import init_logger # Import the new logger

# Initialize logger
# It's good practice to initialize logging early.
# The level can be adjusted by args if needed, or by environment variables.
init_logger("INFO")
logger = logging.getLogger(__name__)

# Simplified comment: Asynchronously run the workflow (command line mode)
async def run_cli_workflow(query: str, thread_id: str = "cli_thread"):
    """
    Runs a simplified workflow in command line mode.
    """
    # Simplified comment: Configure graph input
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }
    # Simplified comment: Define initial state
    initial_state: State = {
        "messages": [{"role": "user", "content": query}],
        "auto_accepted_plan": True, # Command line mode defaults to auto-accepting plans
        "enable_background_investigation": True,
        "output_options": ["pdf", "ppt"], # Example: Request PDF and PPT output
        "output_dir": "./output_cli_reports", # Example: Specify output directory for CLI
        # Other default values for command line mode can be added here
    }

    logger.info(f"--- [CLI Mode] Starting to process query: {query} ---")

    # Simplified comment: Asynchronously execute the graph and print events
    async for event in graph.astream(initial_state, config=config):
        # Print output of each node for debugging
        for node_name, node_output in event.items():
            logger.info(f"--- [Node: {node_name}] ---")
            # Filter out some lengthy fields to keep the output clean
            if isinstance(node_output, dict):
                # Access 'values' if it's a State object or similar structure
                current_values = node_output.get('values', node_output) if hasattr(node_output, 'get') else node_output

                # Ensure current_values is a dictionary before proceeding
                if not isinstance(current_values, dict):
                    logger.info(current_values)
                    print("
" + "="*30 + "
")
                    continue

                filtered_value = {k: v for k, v in current_values.items() if k not in ["messages", "config", "current_plan"]}
                if filtered_value:
                    logger.info(filtered_value)
            else:
                logger.info(node_output)
            print("
" + "="*30 + "
") # Keep print for console visibility of progress

    # Simplified comment: Get and print the final report
    try:
        final_state_values = await graph.aget_state(config)
        # The state returned by aget_state is an object with a 'values' attribute
        final_report = final_state_values.values.get("final_report", "Could not generate final report.")
        pdf_path = final_state_values.values.get("pdf_path")
        ppt_path = final_state_values.values.get("ppt_path")

        logger.info("--- [Final Report] ---")
        logger.info(final_report)
        if pdf_path:
            logger.info(f"PDF report generated at: {pdf_path}")
        if ppt_path:
            logger.info(f"PPT report generated at: {ppt_path}")

    except Exception as e:
        logger.error(f"Error getting final state or report: {e}")
        logger.info("--- [Final Report] ---")
        logger.info("Could not generate final report due to an error.")


# Simplified comment: Main function
def main():
    # Simplified comment: Set up command line argument parsing
    parser = argparse.ArgumentParser(
        description="DeepFlow Agent Workflow Project",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start FastAPI server to provide API service."
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Directly run a query in command line mode."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="API server host address."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API server port number."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging for CLI mode."
    )
    args = parser.parse_args()

    if args.debug:
        init_logger("DEBUG") # Set logger to DEBUG if --debug is used
        logger.setLevel(logging.DEBUG) # Also set the specific logger instance level

    # Simplified comment: Select startup mode based on arguments
    if args.serve:
        logger.info(f"--- [Service Mode] Starting FastAPI server at http://{args.host}:{args.port} ---")
        # Note: Uvicorn has its own logging configuration.
        # Our init_logger will apply to application logs, not necessarily Uvicorn's server logs.
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.query:
        asyncio.run(run_cli_workflow(args.query))
    else:
        # Simplified comment: Print help message if no mode is specified
        logger.warning("Error: Please specify a run mode.")
        parser.print_help()

if __name__ == "__main__":
    main()
