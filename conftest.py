"""
Pytest configuration for VPS-Agent tests.
Adds core/ to Python path for imports.
"""
import sys
import os

# Add core/ directory to path for imports
core_path = os.path.join(os.path.dirname(__file__), 'core')
if core_path not in sys.path:
    sys.path.insert(0, core_path)
