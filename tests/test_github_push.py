"""TDD tests for GitHub auto-push functionality."""
from __future__ import annotations
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.exporters.static_exporter import push_to_github


def test_push_skips_when_no_credentials(tmp_path, monkeypatch):
    """Without GITHUB_TOKEN, push should skip gracefully."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("UNISCOLIAN_REPO_URL", raising=False)
    result = push_to_github(tmp_path, "test message")
    assert result["pushed"] is False
    assert "credentials" in result.get("reason", "").lower()


def test_push_skips_when_no_repo_url(tmp_path, monkeypatch):
    """With token but no repo URL, push should skip."""
    monkeypatch.setenv("GITHUB_TOKEN", "test_token_123")
    monkeypatch.delenv("UNISCOLIAN_REPO_URL", raising=False)
    result = push_to_github(tmp_path, "test message")
    assert result["pushed"] is False


def test_push_skips_when_no_changes(tmp_path, monkeypatch):
    """If git status shows no changes, skip commit+push."""
    monkeypatch.setenv("GITHUB_TOKEN", "test_token_123")
    monkeypatch.setenv("UNISCOLIAN_REPO_URL", 
                       "https://github.com/user/repo.git")
    
    def mock_run(cmd, **kwargs):
        m = MagicMock()
        if len(cmd) > 1 and cmd[1] == "status":
            m.stdout = ""
            m.returncode = 0
        elif len(cmd) > 2 and cmd[1] == "remote" and cmd[2] == "get-url":
            m.returncode = 1
            m.stdout = ""
        else:
            m.returncode = 0
            m.stdout = ""
        return m
    
    with patch("core.exporters.static_exporter.subprocess.run", 
               side_effect=mock_run):
        result = push_to_github(tmp_path, "test")
    assert result["pushed"] is False
    assert "changes" in result.get("reason", "").lower()


def test_push_success_returns_true(tmp_path, monkeypatch):
    """Successful push should return pushed=True."""
    monkeypatch.setenv("GITHUB_TOKEN", "test_token_123")
    monkeypatch.setenv("UNISCOLIAN_REPO_URL", 
                       "https://github.com/user/repo.git")
    
    calls = []
    def mock_run(cmd, **kwargs):
        calls.append(cmd)
        m = MagicMock()
        if len(cmd) > 1 and cmd[1] == "status":
            m.stdout = "M  file.txt\n"
            m.returncode = 0
        elif len(cmd) > 1 and cmd[1] == "push":
            m.stdout = "pushed successfully"
            m.returncode = 0
        elif len(cmd) > 2 and cmd[1] == "remote" and cmd[2] == "get-url":
            m.returncode = 1
            m.stdout = ""
        else:
            m.returncode = 0
            m.stdout = ""
        return m
    
    with patch("core.exporters.static_exporter.subprocess.run", 
               side_effect=mock_run):
        result = push_to_github(tmp_path, "feat: new post")
    
    assert result["pushed"] is True
    cmd_names = [c[1] for c in calls if len(c) > 1]
    assert "add" in cmd_names
    assert "commit" in cmd_names
    assert "push" in cmd_names
    push_calls = [c for c in calls if len(c) > 1 and c[1] == "push"]
    assert any("--force" in c for c in push_calls)


def test_push_uses_force_flag(tmp_path, monkeypatch):
    """Verify git push uses --force flag."""
    monkeypatch.setenv("GITHUB_TOKEN", "test_token")
    monkeypatch.setenv("UNISCOLIAN_REPO_URL", "https://github.com/user/repo.git")
    
    executed_commands = []
    def mock_run(cmd, **kwargs):
        executed_commands.append(cmd)
        m = MagicMock()
        if len(cmd) > 1 and cmd[1] == "status":
            m.stdout = "M file.txt\n"
            m.returncode = 0
        elif len(cmd) > 1 and cmd[1] == "push":
            m.returncode = 0
            m.stdout = "pushed"
        elif len(cmd) > 2 and cmd[1] == "remote" and cmd[2] == "get-url":
            m.returncode = 1
        else:
            m.returncode = 0
        return m

    with patch("core.exporters.static_exporter.subprocess.run", side_effect=mock_run):
        push_to_github(tmp_path, "test force")
    
    push_cmds = [cmd for cmd in executed_commands if "push" in cmd]
    assert any("--force" in cmd for cmd in push_cmds), f"Commands executed: {executed_commands}"


def test_push_uses_authenticated_url(tmp_path, monkeypatch):
    """Token must be embedded in HTTPS URL for authentication."""
    monkeypatch.setenv("GITHUB_TOKEN", "my_secret_token")
    monkeypatch.setenv("UNISCOLIAN_REPO_URL", 
                       "https://github.com/user/repo.git")
    
    captured_urls = []
    def mock_run(cmd, **kwargs):
        for c in cmd:
            if "github.com" in str(c):
                captured_urls.append(str(c))
        m = MagicMock()
        if len(cmd) > 1 and cmd[1] == "status":
            m.stdout = "M file.txt\n"
        elif len(cmd) > 1 and cmd[1] == "push":
            m.returncode = 0
        elif len(cmd) > 2 and cmd[1] == "remote" and cmd[2] == "get-url":
            m.returncode = 1
        else:
            m.returncode = 0
        m.stdout = ""
        return m
    
    with patch("core.exporters.static_exporter.subprocess.run", 
               side_effect=mock_run):
        push_to_github(tmp_path, "test")
    
    assert any("my_secret_token@github.com" in url 
               for url in captured_urls), f"Token not in URLs: {captured_urls}"


def test_push_handles_git_not_installed(tmp_path, monkeypatch):
    """If git command not found, should fail gracefully."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("UNISCOLIAN_REPO_URL", "https://github.com/u/r.git")
    
    with patch("core.exporters.static_exporter.subprocess.run",
               side_effect=FileNotFoundError("git not found")):
        result = push_to_github(tmp_path, "test")
    
    assert result["pushed"] is False
    assert "error" in result


def test_push_handles_push_failure(tmp_path, monkeypatch):
    """If git push fails (e.g., auth error), return error gracefully."""
    monkeypatch.setenv("GITHUB_TOKEN", "bad_token")
    monkeypatch.setenv("UNISCOLIAN_REPO_URL", 
                       "https://github.com/user/repo.git")
    
    def mock_run(cmd, **kwargs):
        m = MagicMock()
        if len(cmd) > 1 and cmd[1] == "status":
            m.stdout = "M file.txt\n"
            m.returncode = 0
        elif len(cmd) > 1 and cmd[1] == "push":
            m.stdout = ""
            m.stderr = "Authentication failed"
            m.returncode = 128
        elif len(cmd) > 2 and cmd[1] == "remote" and cmd[2] == "get-url":
            m.returncode = 1
            m.stdout = ""
        else:
            m.returncode = 0
            m.stdout = ""
        return m
    
    with patch("core.exporters.static_exporter.subprocess.run", 
               side_effect=mock_run):
        result = push_to_github(tmp_path, "test")
    
    assert result["pushed"] is False
    assert "error" in result or "failed" in str(result).lower()


def test_push_handles_timeout(tmp_path, monkeypatch):
    """If push takes too long (>120s), should timeout gracefully."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("UNISCOLIAN_REPO_URL", 
                       "https://github.com/user/repo.git")
    
    def mock_run(cmd, **kwargs):
        m = MagicMock()
        if len(cmd) > 1 and cmd[1] == "status":
            m.stdout = "M file.txt\n"
            m.returncode = 0
        elif len(cmd) > 1 and cmd[1] == "push":
            raise subprocess.TimeoutExpired(cmd, 120)
        elif len(cmd) > 2 and cmd[1] == "remote" and cmd[2] == "get-url":
            m.returncode = 1
            m.stdout = ""
        else:
            m.returncode = 0
            m.stdout = ""
        return m
    
    with patch("core.exporters.static_exporter.subprocess.run", 
               side_effect=mock_run):
        result = push_to_github(tmp_path, "test")
    
    assert result["pushed"] is False
