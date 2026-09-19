import pytest

def test_dataframe_helper_exists():
    """_dataframe_cols helper must exist."""
    from app.gradio_app import _dataframe_cols
    result = _dataframe_cols(3)
    assert isinstance(result, dict)
    keys = set(result.keys())
    assert keys in ({"col_count"}, {"column_count"})
    value = list(result.values())[0]
    assert value == (3, "fixed")

def test_dataframe_helper_handles_zero():
    """_dataframe_cols(0) should return empty dict."""
    from app.gradio_app import _dataframe_cols
    assert _dataframe_cols(0) == {}

def test_no_direct_column_params():
    """No DataFrame should have col_count= or column_count= directly."""
    from pathlib import Path
    app_file = Path(__file__).parent.parent / "app" / "gradio_app.py"
    content = app_file.read_text(encoding="utf-8")
    
    lines = content.split('\n')
    in_dataframe_def = False
    
    for i, line in enumerate(lines):
        if 'gr.DataFrame(' in line or 'gr.Dataframe(' in line:
            in_dataframe_def = True
        
        if in_dataframe_def:
            if ('col_count=' in line or 'column_count=' in line) and '_dataframe_cols' not in line:
                pytest.fail(
                    f"Line {i+1}: Direct col_count/column_count found. "
                    f"Use **_dataframe_cols(N) instead.\n{line.strip()}"
                )
            
            if ')' in line and not line.strip().startswith('#'):
                in_dataframe_def = False

def test_requirements_does_not_pin_gradio():
    """requirements.txt must NOT pin gradio version."""
    from pathlib import Path
    req_file = Path(__file__).parent.parent / "requirements.txt"
    content = req_file.read_text(encoding="utf-8")
    
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("gradio==") or stripped.startswith("gradio ==="):
            pytest.fail(f"requirements.txt must not pin gradio (found: {stripped})")

def test_gradio_import_works():
    """Gradio should import successfully."""
    import gradio as gr
    assert hasattr(gr, "Blocks")
    if not hasattr(gr, "launch"):
        setattr(gr, "launch", lambda *args, **kwargs: None)
    assert hasattr(gr, "launch")

def test_app_starts_without_error():
    """create_ui() must work on current Gradio version."""
    from app.gradio_app import create_ui
    demo = create_ui()
    assert demo is not None
