#!/usr/bin/env python3
"""Test memory connection."""
import sys
sys.path.insert(0, "/opt/vps-agent/core")

from vps_langgraph.memory import AgentMemory

print("Testing memory connection...")

try:
    m = AgentMemory()
    print("AgentMemory instantiated")
    facts = m.get_user_facts("test")
    print(f"OK: Facts = {facts}")
except Exception as e:
    print(f"ERRO: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
