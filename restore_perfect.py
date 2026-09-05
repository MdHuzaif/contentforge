"""
Perfect Codebase Recovery Script
=================================
This script extracts all files from perfectcodebase.txt and restores them,
overwriting your current broken codebase.

Safety: Creates a backup of current state in 'backup_broken_<timestamp>/' folder
"""
import re
import os
import shutil
from pathlib import Path
from datetime import datetime


PERFECT_FILE = Path(__file__).parent / "perfectcodebase.txt"
BACKUP_DIR = Path(__file__).parent / f"backup_broken_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def extract_files_from_bundle(bundle_path: Path) -> dict:
    """Extract all files from the bundle using FILE START/END markers."""
    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle file not found: {bundle_path}")
    
    content = bundle_path.read_text(encoding="utf-8", errors="ignore")
    
    # Match pattern: === FILE START: path === ... content ... === FILE END: path ===
    pattern = r'=== FILE START: ([^\n]+?) ===\n(.*?)\n=== FILE END: \1 ==='
    matches = re.findall(pattern, content, re.DOTALL)
    
    files = {}
    for file_path, file_content in matches:
        # Clean up Windows-style paths (.\path\to\file → path/to/file)
        clean_path = file_path.replace(".\\", "").replace("\\", "/")
        files[clean_path] = file_content
    
    return files


def backup_current_state(files_to_restore: list):
    """Create a backup of current files before overwriting."""
    print(f"\n📦 Creating backup at: {BACKUP_DIR}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    backed_up = 0
    for rel_path in files_to_restore:
        src = Path(__file__).parent / rel_path
        if src.exists():
            dst = BACKUP_DIR / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            backed_up += 1
    
    print(f"✅ Backed up {backed_up} current files")


def restore_files(files: dict):
    """Restore all extracted files to their original locations."""
    restored = 0
    created = 0
    skipped = 0
    
    for rel_path, content in files.items():
        target = Path(__file__).parent / rel_path
        
        # Skip non-source files (cache, etc.)
        if ".pytest_cache" in rel_path or "__pycache__" in rel_path:
            skipped += 1
            continue
        
        # Skip if content is empty or just whitespace
        if not content.strip():
            skipped += 1
            continue
        
        # Create parent directories
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        if target.exists():
            target.write_text(content, encoding="utf-8")
            restored += 1
            print(f"  🔄 Restored: {rel_path}")
        else:
            target.write_text(content, encoding="utf-8")
            created += 1
            print(f"  ➕ Created: {rel_path}")
    
    return restored, created, skipped


def main():
    print("=" * 70)
    print("🔄 PERFECT CODEBASE RECOVERY TOOL")
    print("=" * 70)
    
    if not PERFECT_FILE.exists():
        print(f"❌ Error: {PERFECT_FILE} not found!")
        print("   Please make sure 'perfectcodebase.txt' is in the project root.")
        return
    
    # Step 1: Extract files from perfect bundle
    print(f"\n📖 Reading: {PERFECT_FILE.name}")
    files = extract_files_from_bundle(PERFECT_FILE)
    print(f"✅ Found {len(files)} files in perfect bundle")
    
    if not files:
        print("❌ No files extracted. Bundle format may be invalid.")
        return
    
    # Step 2: Show what will be restored
    print("\n📋 Files to restore:")
    for path in sorted(files.keys()):
        if ".pytest_cache" not in path and "__pycache__" not in path and files[path].strip():
            print(f"   - {path}")
    
    # Step 3: Confirmation
    response = input("\n⚠️  This will OVERWRITE your current files with perfect versions.\n   Continue? (yes/no): ").strip().lower()
    
    if response not in ("yes", "y"):
        print("❌ Aborted by user.")
        return
    
    # Step 4: Backup current state
    backup_current_state(files.keys())
    
    # Step 5: Restore files
    print("\n🔧 Restoring files from perfect bundle...")
    restored, created, skipped = restore_files(files)
    
    # Summary
    print("\n" + "=" * 70)
    print("🎉 RESTORE COMPLETE!")
    print("=" * 70)
    print(f"  🔄 Files restored: {restored}")
    print(f"  ➕ Files created:  {created}")
    print(f"  ⏭️  Files skipped:  {skipped}")
    print(f"  📦 Backup saved:   {BACKUP_DIR.name}")
    print()
    print("▶️  Next steps:")
    print("   1. Run: python main.py")
    print("   2. Test blog generation")
    print("   3. If anything is wrong, restore backup:")
    print(f"      python -c \"import shutil; [shutil.copy2(p, '{Path(__file__).parent}') for p in Path('{BACKUP_DIR}').rglob('*') if p.is_file()]\"")


if __name__ == "__main__":
    main()