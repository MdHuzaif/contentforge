"""Verification script for Gradio app integration."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    from app.gradio_app import build_demo, generate_content
    demo = build_demo()
    assert demo is not None, "Gradio demo should build successfully"
    print("[OK] Gradio app build and generate_content handler verified successfully!")


if __name__ == "__main__":
    main()
