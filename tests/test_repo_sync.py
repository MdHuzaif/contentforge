"""Tests for site repo sync logic."""
from __future__ import annotations
from unittest.mock import patch, MagicMock
import pytest

from core.exporters.repo_sync import ensure_site_repo


def test_existing_content_returns_without_clone(tmp_path, monkeypatch):
    """If folder already has content, do nothing (local dev safe)."""
    (tmp_path / "index.html").write_text("<html></html>")
    monkeypatch.setattr("core.exporters.repo_sync.UNISCOLIAN_ROOT", tmp_path)
    monkeypatch.setenv("SPACE_ID", "user/space")
    with patch("core.exporters.repo_sync.subprocess.run") as mock_run:
        result = ensure_site_repo()
    mock_run.assert_not_called()
    assert result == tmp_path


def test_empty_folder_on_hf_triggers_clone(tmp_path, monkeypatch):
    """On HF with empty folder + creds, shallow clone must run."""
    monkeypatch.setattr("core.exporters.repo_sync.UNISCOLIAN_ROOT", tmp_path)
    monkeypatch.setenv("SPACE_ID", "user/space")
    monkeypatch.setenv("GITHUB_TOKEN", "tok123")
    monkeypatch.setenv("UNISCOLIAN_REPO_URL", "https://github.com/u/r.git")
    with patch("core.exporters.repo_sync.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ensure_site_repo()
    args = mock_run.call_args[0][0]
    assert args[0:3] == ["git", "clone", "--depth"]
    # token must be embedded but never logged
    assert any("tok123@github.com" in str(a) for a in args)


def test_empty_folder_local_no_clone(tmp_path, monkeypatch):
    """Local dev without SPACE_ID must NOT clone, just mkdir."""
    missing = tmp_path / "site"
    monkeypatch.setattr("core.exporters.repo_sync.UNISCOLIAN_ROOT", missing)
    monkeypatch.delenv("SPACE_ID", raising=False)
    monkeypatch.delenv("HF_SPACE_ID", raising=False)
    with patch("core.exporters.repo_sync.subprocess.run") as mock_run:
        result = ensure_site_repo()
    mock_run.assert_not_called()
    assert result == missing
    assert missing.exists()
