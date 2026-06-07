import os
import py_compile

def check_syntax():
    has_error = False
    for root, dirs, files in os.walk('.'):
        # Skip virtual environments
        if '.venv' in root or 'venv' in root or '.git' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    py_compile.compile(path, doraise=True)
                except py_compile.PyCompileError as e:
                    print(f"Syntax Error in {path}:")
                    print(e)
                    has_error = True
                except Exception as e:
                    print(f"Error compiling {path}: {e}")
                    has_error = True
    if not has_error:
        print("All Python files have valid syntax.")
    else:
        exit(1)

if __name__ == '__main__':
    check_syntax()
