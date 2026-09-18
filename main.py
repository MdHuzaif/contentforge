import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the Gradio application
from app.gradio_app import launch
from app.config import logger

# Verify Gradio version at startup (catches HF pip issues)
import gradio as gr

_gradio_version = tuple(int(x) for x in gr.__version__.split(".")[:2])
if _gradio_version >= (5, 20):
    logger.warning(
        "⚠️ Gradio %s detected (known schema bug). "
        "If API errors occur, pin gradio==5.12.0 in requirements.txt",
        gr.__version__
    )
else:
    logger.info("✅ Gradio %s (stable schema handling)", gr.__version__)

if __name__ == "__main__":
    try:
        from core.exporters.repo_sync import ensure_site_repo
        ensure_site_repo()
    except Exception as e:
        logger.warning("Site repo sync skipped: %s", e)
    launch()