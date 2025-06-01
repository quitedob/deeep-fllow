# FilePath: src/utils/logging.py
# -*- coding: utf-8 -*-
"""
Unified logging configuration to avoid conflicts with multiple basicConfig calls.
"""
import logging
import os

def init_logger(level:str="INFO"):
    # Convert string level to logging level constant
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S" # Added date format for consistency
    )
    # Suppress excessive logging from third-party libraries
    noisy_libraries = ["httpx", "urllib3", "httpcore", "openai", "asyncio"] # Added more common noisy libraries
    for noisy_lib in noisy_libraries:
        logging.getLogger(noisy_lib).setLevel(logging.WARNING)

# Example usage (can be removed or kept for testing):
# if __name__ == '__main__':
#     init_logger("DEBUG")
#     logging.debug("This is a debug message.")
#     logging.info("This is an info message.")
#     logging.warning("This is a warning message.")
#     # Example of a noisy library logger (if it were active)
#     logging.getLogger("httpx").warning("This is a httpx test warning, should be visible.")
#     logging.getLogger("httpx").info("This is a httpx test info, should be suppressed.")
