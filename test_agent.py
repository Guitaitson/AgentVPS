#!/usr/bin/env python3
"""Test script for LangGraph agent."""
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'core'))

# Import from the package
from vps_agent.agent import process_message_async
import asyncio


def test_process_message():
    """Test basic message processing."""
    result = asyncio.run(process_message_async('123456789', 'test message'))
    print('Result:', result)
    assert result is not None


if __name__ == "__main__":
    test_process_message()
