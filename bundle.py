import os

output_file = 'codebase_bundle.txt'
# Directories and extensions to skip
exclude_dirs = {'.git', '__pycache__', 'venv', 'env', '.idea', 'build', 'dist'}
include_extensions = {'.py', '.html', '.css', '.js', '.json', '.txt', '.md'}

with open(output_file, 'w', encoding='utf-8') as outfile:
    for root, dirs, files in os.walk('.'):
        # Modify dirs in-place to skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if any(file.endswith(ext) for ext in include_extensions):
                if file == output_file or file == 'bundle.py':
                    continue
                file_path = os.path.join(root, file)
                outfile.write(f'=== FILE START: {file_path} ===\n')
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f'[Error reading file: {e}]')
                outfile.write(f'\n=== FILE END: {file_path} ===\n\n')

print(f'Codebase successfully bundled into {output_file}')