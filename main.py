import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the Gradio application
from app.gradio_app import launch
from app.config import logger

# Version check — show_api=False handles schema bugs in all versions
try:
    _gradio_version = tuple(int(x) for x in gr.__version__.split(".")[:2])
    logger.info("✅ Gradio %s loaded (show_api=False active for schema safety)", 
                gr.__version__)
except Exception:
    logger.info("✅ Gradio loaded (version check skipped)")

if __name__ == "__main__":
    try:
        from core.exporters.repo_sync import ensure_site_repo
        ensure_site_repo()
    except Exception as e:
        logger.warning("Site repo sync skipped: %s", e)
    launch()