import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables as early as possible
load_dotenv()

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("contentforge")

# ============ API Keys (Gemini-only) ============
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# ============ Path Setup ============
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
SOP_DATA_DIR = DATA_DIR / "SOP"
TOPICS_DIR = DATA_DIR / "topics"
RESULTS_DIR = BASE_DIR / "results"
CONTENT_OUTPUT_DIR = BASE_DIR / "content_output"
BLOGS_DIR = CONTENT_OUTPUT_DIR / "blogs"
IMAGES_DIR = CONTENT_OUTPUT_DIR / "images"
VIDEOS_DIR = CONTENT_OUTPUT_DIR / "videos"
MEMORY_DIR = BASE_DIR / "backend" / "memory"

# Ensure all directories exist
for _d in [
    DATA_DIR, SOP_DATA_DIR, TOPICS_DIR,
    RESULTS_DIR, CONTENT_OUTPUT_DIR, BLOGS_DIR, IMAGES_DIR, VIDEOS_DIR,
    MEMORY_DIR,
]:
    _d.mkdir(parents=True, exist_ok=True)

# Short-term memory (SQLite)
SHORTTERM_MEMORY_DIR = MEMORY_DIR / "shortterm_memory"
SHORTTERM_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_DB_PATH = SHORTTERM_MEMORY_DIR / "contentforge.db"

# Prompt registry
PROMPT_REGISTRY_DIR = MEMORY_DIR / "prompt_registry"
PROMPT_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)

# ============ UI / Server Controls ============
APP_TITLE = "ContentForge AI"
GRADIO_SERVER_NAME = os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1")
GRADIO_SERVER_PORT = int(os.environ.get("GRADIO_SERVER_PORT", "7860"))

# ===== Uniscolian Static Site Integration (Level 8) =====
UNISCOLIAN_ROOT = Path(os.environ.get("UNISCOLIAN_ROOT", str(BASE_DIR.parent / "uniscolian-website")))
UNISCOLIAN_REFERENCE_SLUG = os.environ.get("UNISCOLIAN_REFERENCE_SLUG", "best-gaming-laptops")
UNISCOLIAN_REFERENCE_POST = UNISCOLIAN_ROOT / UNISCOLIAN_REFERENCE_SLUG / "index.html"
UNISCOLIAN_TEMPLATE_PATH = UNISCOLIAN_ROOT / "_template" / "post_template.html"
UNISCOLIAN_UPLOADS_DIR = UNISCOLIAN_ROOT / "wp-content" / "uploads"
DEFAULT_AUTHOR_NAME = "Huzaif Enan"
DEFAULT_CATEGORY_NAME = "Laptop"
DEFAULT_CATEGORY_SLUG = "laptop"

# ===== Sitemap + Registry (Level 10) =====
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://uniscolian.com")
POST_REGISTRY_PATH = UNISCOLIAN_ROOT / "_template" / "post_registry.json"
RELATED_LINKS_COUNT = int(os.environ.get("RELATED_LINKS_COUNT", "2"))