"""ContentForge AI - Entry point."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import gradio as gr
from app.config import logger

# Version check
try:
    logger.info("✅ Gradio %s loaded", gr.__version__)
except Exception:
    logger.info("✅ Gradio loaded")

# CRITICAL: Import GPU stub so HF ZeroGPU detects @spaces.GPU function
try:
    from app.gpu_stub import gpu_heartbeat  # noqa: F401
    logger.info("✅ GPU stub loaded (HF ZeroGPU compatibility)")
except Exception as e:
    logger.warning("GPU stub load skipped: %s", e)

# Site repo sync (HF only)
try:
    from core.exporters.repo_sync import ensure_site_repo
    ensure_site_repo()
except Exception as e:
    logger.warning("Site repo sync skipped: %s", e)

# Import and build demo (global variable needed for HF hot reload)
from app.gradio_app import create_ui, launch

# Global demo for Gradio hot reload mode (HF uses this)
demo = create_ui()

if __name__ == "__main__":
    launch()
