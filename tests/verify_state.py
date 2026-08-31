"""Verification script for core/state.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    from core.state import ContentForgeState, create_initial_state
    state = create_initial_state(topic="Test topic")
    assert state["user_request"] == "Test topic"
    assert "content_structure" in state
    assert state["operations_count"] == 0
    print("[OK] core/state.py verified successfully!")


if __name__ == "__main__":
    main()
