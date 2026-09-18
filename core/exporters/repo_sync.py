"""Ensure the uniscolian-website repo exists locally (clone on HF Space)."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path

from app.config import UNISCOLIAN_ROOT, logger


def ensure_site_repo() -> Path:
    """Make sure UNISCOLIAN_ROOT exists with site content.

    On Hugging Face (SPACE_ID set): shallow-clone the GitHub repo if the
    folder is missing/empty, so templates + existing posts are available.
    On local dev: never clone, just ensure the folder exists.
    """
    root = Path(UNISCOLIAN_ROOT)
    token = os.environ.get("GITHUB_TOKEN", "")
    repo_url = os.environ.get("UNISCOLIAN_REPO_URL", "")
    on_hf = bool(os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID"))

    has_content = root.exists() and any(root.iterdir())
    if has_content:
        return root  # local dev or already cloned

    if on_hf and token and repo_url:
        try:
            root.parent.mkdir(parents=True, exist_ok=True)
            auth_url = repo_url.replace(
                "https://github.com/", f"https://{token}@github.com/"
            )
            logger.info("📥 Cloning site repo into %s (shallow)...", root)
            result = subprocess.run(
                ["git", "clone", "--depth", "1", auth_url, str(root)],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                logger.info("✅ Site repo cloned successfully")
                return root
            logger.error("❌ Clone failed: %s", result.stderr)
        except Exception as e:
            logger.error("❌ Clone error: %s", e)

    # Fallback: just create empty folder so app doesn't crash
    root.mkdir(parents=True, exist_ok=True)
    return root
