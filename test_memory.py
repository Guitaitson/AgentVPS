#!/usr/bin/env python3
"""Test memory connection."""
import sys
from pathlib import Path

# Add the project root to the path for development mode
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.vps_langgraph.memory import AgentMemory


def test_memory():
    """Test memory connection."""
    print("Testing memory connection...")

    try:
        m = AgentMemory()
        print("AgentMemory instantiated")
        facts = m.get_user_facts("test")
        print(f"OK: Facts = {facts}")
        return True
    except Exception as e:
        print(f"ERRO: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_memory()
