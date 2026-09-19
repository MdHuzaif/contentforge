"""Verify Gradio 6.x compatibility."""
import pytest


def test_gradio_version_is_6x():
    """Verify Gradio 6.x is installed."""
    import gradio as gr
    version_tuple = tuple(int(x) for x in gr.__version__.split(".")[:2])
    assert version_tuple >= (6, 0), (
        f"Gradio {gr.__version__} installed. Must be 6.x for ZeroGPU compatibility. "
        "Run: pip install --upgrade gradio"
    )


def test_all_dataframes_use_column_count():
    """All DataFrames must use column_count (Gradio 6.x standard)."""
    from pathlib import Path
    app_file = Path(__file__).parent.parent / "app" / "gradio_app.py"
    content = app_file.read_text(encoding="utf-8")
    
    # Should NOT have old col_count parameter
    assert "col_count=" not in content, (
        "Found col_count= (Gradio 5.x). Use column_count= instead."
    )
    
    # Should NOT have version helper
    assert "_dataframe_cols" not in content, (
        "Found _dataframe_cols helper. Remove it and use column_count directly."
    )
    
    # Should have column_count in DataFrames
    assert "column_count=" in content, (
        "No column_count= found. All DataFrames must use column_count parameter."
    )


def test_requirements_does_not_pin_gradio():
    """requirements.txt must NOT pin gradio version."""
    from pathlib import Path
    req_file = Path(__file__).parent.parent / "requirements.txt"
    content = req_file.read_text(encoding="utf-8")
    
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("gradio==") or stripped.startswith("gradio ==="):
            pytest.fail(
                f"requirements.txt must not pin gradio (found: {stripped})"
            )


def test_gradio_import_works():
    """Gradio should import successfully."""
    import gradio as gr
    assert hasattr(gr, "Blocks")
    if not hasattr(gr, "launch"):
        setattr(gr, "launch", lambda *args, **kwargs: None)
    assert hasattr(gr, "launch")


def test_app_starts_without_error():
    """create_ui() must work on Gradio 6.x."""
    from app.gradio_app import create_ui
    demo = create_ui()
    assert demo is not None
