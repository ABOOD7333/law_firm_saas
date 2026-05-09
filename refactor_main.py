import os
import re

MAIN_PY_PATH = 'main.py'
ROUTERS_DIR = 'routers'
CORE_DIR = 'core'

def create_dirs():
    os.makedirs(ROUTERS_DIR, exist_ok=True)
    open(os.path.join(ROUTERS_DIR, '__init__.py'), 'w').close()
    
    os.makedirs(CORE_DIR, exist_ok=True)
    open(os.path.join(CORE_DIR, '__init__.py'), 'w').close()

def extract_dependencies(content):
    # We will extract get_current_user, _hash_pin, _verify_pin to core/security.py
    # But to keep it simple and avoid circular imports, let's keep get_current_user in main.py for now
    # and in routers we do: `from main import get_current_user, templates`
    pass

def split_main_py():
    with open(MAIN_PY_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to find sections: # ============ [NAME] ============
    # We will split the file by these headers
    sections = re.split(r'# ============ (.*?) ============', content)
    
    # sections[0] is the top of the file (imports, setup, auth)
    header_content = sections[0]
    
    # Ensure routers are imported at the bottom of header_content, before uvicorn.run
    
    router_imports = []
    app_includes = []
    
    # Process sections
    for i in range(1, len(sections), 2):
        section_name = sections[i].strip()
        section_code = sections[i+1]
        
        # Determine filename
        filename = section_name.lower().replace(' ', '_').replace('/', '_') + '.py'
        if 'routes' in filename:
            filename = filename.replace('_routes', '')
            
        filepath = os.path.join(ROUTERS_DIR, filename)
        
        # Prepare router code
        router_code = f"""from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import json
import traceback

from database.database import get_db
from database.models import *

# نستخدم الاستيراد المتأخر لتجنب التكرار (Circular Imports)
from main import get_current_user, templates

router = APIRouter()

"""
        
        # Replace @app.get with @router.get
        section_code = re.sub(r'@app\.', '@router.', section_code)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(router_code + section_code.split('if __name__ == "__main__":')[0])
            
        module_name = filename.replace('.py', '')
        router_imports.append(f"from routers import {module_name}")
        app_includes.append(f"app.include_router({module_name}.router)")

    # Reconstruct main.py
    new_main_content = header_content
    
    new_main_content += "\n# ============ ROUTERS INTEGRATION ============\n"
    new_main_content += "\n".join(router_imports) + "\n\n"
    new_main_content += "\n".join(app_includes) + "\n\n"
    
    if 'if __name__ == "__main__":' in content:
        new_main_content += 'if __name__ == "__main__":\n    import uvicorn\n    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)\n'

    # Backup original
    os.rename(MAIN_PY_PATH, MAIN_PY_PATH + '.backup')
    
    # Write new main.py
    with open(MAIN_PY_PATH, 'w', encoding='utf-8') as f:
        f.write(new_main_content)

if __name__ == '__main__':
    print("Starting refactoring...")
    create_dirs()
    split_main_py()
    print("Refactoring completed successfully! A backup of main.py was saved as main.py.backup.")
