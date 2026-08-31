"""Utility helpers for managing per-task result directories."""
from __future__ import annotations

import contextvars
import shutil
from pathlib import Path
from typing import List, Optional

RESULTS_ROOT = Path("results")
RESULTS_ROOT.mkdir(parents=True, exist_ok=True)

_task_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "contentforge_task_id",
    default=None,
)


def get_results_root() -> Path:
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    return RESULTS_ROOT


def set_current_task_id(task_id: Optional[str]):
    if task_id is None:
        return None
    return _task_id_var.set(task_id)


def reset_current_task_id(token) -> None:
    if token is None:
        return
    _task_id_var.reset(token)


def get_current_task_id() -> Optional[str]:
    return _task_id_var.get()


def ensure_task_dir(task_id: Optional[str] = None) -> Path:
    tid = task_id or get_current_task_id()
    if not tid:
        return get_results_root()
    path = get_results_root() / tid
    path.mkdir(parents=True, exist_ok=True)
    return path


def task_file_path(
    filename: str,
    *,
    task_id: Optional[str] = None,
) -> Path:
    folder = ensure_task_dir(task_id)
    return folder / filename


def list_task_files(task_id: str) -> List[Path]:
    base_dir = ensure_task_dir(task_id)
    files = [p for p in base_dir.rglob("*") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def remove_task_dir(task_id: str) -> None:
    directory = get_results_root() / task_id
    if directory.exists():
        shutil.rmtree(directory, ignore_errors=True)