#!/usr/bin/env python3
"""Test script for LangGraph agent."""
import sys
sys.path.insert(0, '/opt/vps-agent/core')

from vps_agent.agent import process_message_async
import asyncio

if __name__ == "__main__":
    result = asyncio.run(process_message_async('123456789', 'test message'))
    print('Result:', result)
