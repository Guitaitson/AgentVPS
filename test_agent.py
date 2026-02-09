#!/usr/bin/env python3
"""Test script for LangGraph agent."""
import sys
from pathlib import Path

# Add the project root to the path for development mode
# When the package is installed via pip install -e ., this is not necessary
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import from the package
import asyncio

from core.vps_agent.agent import process_message_async


def test_process_message():
    """Test basic message processing."""
    result = asyncio.run(process_message_async('123456789', 'test message'))
    print('Result:', result)
    assert result is not None


if __name__ == "__main__":
    test_process_message()
