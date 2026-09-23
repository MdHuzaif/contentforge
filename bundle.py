import os

output_file = 'codebase_bundle.txt'

# ১. অপ্রয়োজনীয় ফোল্ডার বাদ দেওয়া
exclude_dirs = {'.git', '__pycache__', 'venv', 'env', '.idea', 'build', 'dist', 'node_modules', '.next', 'coverage', '.vscode'}

# ২. প্রয়োজনীয় এক্সটেনশন
include_extensions = {'.py', '.html', '.css', '.js', '.ts', '.tsx', '.jsx', '.json', '.txt', '.md', '.yaml', '.yml', '.toml'}

# ৩. নির্দিষ্ট কিছু বিরক্তিকর ফাইল বাদ দেওয়া (Lock files)
exclude_files = {'package-lock.json', 'yarn.lock', 'poetry.lock', 'Pipfile.lock', 'bundle.py', output_file}

# ৪. ফাইল সাইজ লিমিট (50 KB) - Minified বা বড় লগ ফাইল স্কিপ করার জন্য
MAX_FILE_SIZE = 50 * 1024 

def generate_tree(directory, prefix=""):
    """প্রজেক্টের একটি ভিজ্যুয়াল ম্যাপ (Tree) তৈরি করার ফাংশন"""
    tree_str = ""
    try:
        entries = sorted([e for e in os.listdir(directory) if e not in exclude_dirs and not e.startswith('.')], key=lambda x: (not os.path.isdir(os.path.join(directory, x)), x.lower()))
    except PermissionError:
        return tree_str
        
    for i, entry in enumerate(entries):
        path = os.path.join(directory, entry)
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        tree_str += f"{prefix}{connector}{entry}\n"
        if os.path.isdir(path):
            extension = "    " if is_last else "│   "
            tree_str += generate_tree(path, prefix + extension)
    return tree_str

with open(output_file, 'w', encoding='utf-8') as outfile:
    # AI-এর জন্য শুরুতে একটি কনটেক্সট সেট করা
    outfile.write("# PROJECT CONTEXT & INSTRUCTIONS FOR AI\n")
    outfile.write("Below is the directory structure of my project, followed by the content of each relevant file.\n")
    outfile.write("Please analyze the architecture and wait for my specific question/task.\n\n")
    
    # ডিরেক্টরি ট্রি (ম্যাপ) যোগ করা
    outfile.write("# DIRECTORY STRUCTURE\n")
    outfile.write("```text\n")
    outfile.write(generate_tree('.'))
    outfile.write("```\n\n")
    
    # ফাইলগুলোর কন্টেন্ট যোগ করা
    outfile.write("# FILE CONTENTS\n\n")
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
        
        for file in sorted(files):
            if not any(file.endswith(ext) for ext in include_extensions):
                continue
            if file in exclude_files:
                continue
                
            file_path = os.path.join(root, file)
            
            # বড় ফাইল স্কিপ করা
            try:
                if os.path.getsize(file_path) > MAX_FILE_SIZE:
                    outfile.write(f'=== FILE START: {file_path} ===\n')
                    outfile.write(f'[Skipped: File is too large ({os.path.getsize(file_path) // 1024} KB) to prevent context overflow]\n')
                    outfile.write(f'=== FILE END: {file_path} ===\n\n')
                    continue
            except OSError:
                continue

            outfile.write(f'=== FILE START: {file_path} ===\n')
            try:
                with open(file_path, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())
            except Exception as e:
                outfile.write(f'[Error reading file: {e}]')
            outfile.write(f'\n=== FILE END: {file_path} ===\n\n')

print(f'✅ Codebase successfully bundled into {output_file}')
