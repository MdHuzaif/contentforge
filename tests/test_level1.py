
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    from app.config import APP_TITLE, DATA_DIR, RESULTS_DIR, SQLITE_DB_PATH

    assert DATA_DIR.exists(), "data/ missing"
    assert RESULTS_DIR.exists(), "results/ missing"
    print("✅ Config OK:", APP_TITLE)
    print("✅ SQLite path:", SQLITE_DB_PATH)

    import gradio
    print("✅ Gradio version:", gradio.__version__)

    from app.gradio_app import build_demo
    build_demo()
    print("✅ Gradio demo builds OK")

    from backend.utils.output_paths import ensure_task_dir, task_file_path
    d = ensure_task_dir("level1_test")
    p = task_file_path("hello.txt", task_id="level1_test")
    p.write_text("ok")
    assert p.exists()
    print("✅ output_paths OK:", p)

    print("\n🎉 LEVEL 1 PASSED — এখন `python main.py` চালাও")


if __name__ == "__main__":
    main()