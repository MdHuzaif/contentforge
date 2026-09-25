"""Verify HF ZeroGPU compatibility setup."""
import pytest
from pathlib import Path


def test_gpu_stub_module_exists():
    """app/gpu_stub.py must exist with gpu_heartbeat function."""
    from app.gpu_stub import gpu_heartbeat
    result = gpu_heartbeat("test")
    assert result == "pong"


def test_main_has_global_demo():
    """main.py must define global 'demo' for HF hot reload."""
    main_file = Path(__file__).parent.parent / "main.py"
    content = main_file.read_text(encoding="utf-8")
    assert "demo = create_ui()" in content or "demo=create_ui()" in content, (
        "main.py must have global 'demo = create_ui()' for HF hot reload"
    )


def test_main_imports_gpu_stub():
    """main.py must import gpu_heartbeat to register GPU function."""
    main_file = Path(__file__).parent.parent / "main.py"
    content = main_file.read_text(encoding="utf-8")
    assert "gpu_heartbeat" in content, (
        "main.py must import gpu_heartbeat from app.gpu_stub"
    )


def test_launch_uses_ssr_mode_false():
    """launch() should disable SSR mode to avoid Node.js restarts."""
    import inspect
    from app.gradio_app import launch
    source = inspect.getsource(launch)
    assert "ssr_mode" in source, (
        "launch() should set ssr_mode parameter"
    )


def test_requirements_has_spaces_package():
    """requirements.txt should include spaces package."""
    req_file = Path(__file__).parent.parent / "requirements.txt"
    content = req_file.read_text(encoding="utf-8")
    assert "spaces" in content.lower(), (
        "requirements.txt should include 'spaces' package for HF GPU stub"
    )
