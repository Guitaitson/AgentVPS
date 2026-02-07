#!/usr/bin/env python3
"""Test script for LangGraph agent."""
import sys
sys.path.insert(0, '/opt/vps-agent/core')

from vps_agent.agent import process_message

# Test with chat message
result = process_message('12345', 'quero conversar')
print('Response:', result)
