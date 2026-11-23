# -*- coding: utf-8 -*-
"""
LawSaaS Technical Map & File Reference Generator
Generates an exhaustive, production-grade HTML book and compiles it into PDF via headless Edge.
"""

import os
import sys
import ast
import json
import subprocess
from datetime import datetime

ROOT_DIR = os.getcwd()

print("Analyzing LawSaaS Project Codebase...")

# 1. Gather all files and categorize them
file_categories = {
    'root_core': {
        'title': 'ملفات الجذر الأساسية والإعدادات (Root Directory Files)',
        'description': 'الملفات التنفيذية الرئيسية، ملفات التكوين، نقاط انطلاق التطبيق، والملفات المرجعية في جذر المشروع.',
        'files': []
    },
    'core_security': {
        'title': 'نواة النظام، الأمان والوسيطات (Core & Security Center)',
        'description': 'الوحدات المركزية لإدارة الأمان، فحص الفيروسات، كشف تضارب المصالح، وسيطات المراقبة، ونظام الاشتراكات.',
        'files': []
    },
    'database_models': {
        'title': 'قاعدة البيانات، النماذج والتهجير (Database & Migrations)',
        'description': 'مخططات الجداول (54 نموذجاً)، نماذج الأمان، إدارة جلسات SQLAlchemy، وملفات ترقية المخططات عبر Alembic.',
        'files': []
    },
    'routers': {
        'title': 'وحدات التوجيه ونقاط النهاية البرمجية (Routers & Endpoints)',
        'description': 'الوحدات البرمجية الـ 43 المسؤولة عن معالجة طلبات المستخدمين لكافة قطاعات النظام القانوني والمالي والإداري.',
        'files': []
    },
    'ai_and_rag': {
        'title': 'محركات الذكاء الاصطناعي والتوليد المعزز (AI & RAG Engines)',
        'description': 'محركات كشف النوايا القانونية، التخاطب مع Google Gemini، الفهرسة المتجهية، واستخراج النصوص عبر OCR.',
        'files': []
    },
    'templates': {
        'title': 'واجهات المستخدم وقوالب العرض (Frontend Templates)',
        'description': 'قوالب Jinja2 التفاعلية (73 قالباً) التي تشكل لوحات التحكم، بوابات الموكلين، النماذج الديناميكية، وبطاقات المتابعة.',
        'files': []
    },
    'static_assets': {
        'title': 'ملفات الأنماط الثابتة والتصميم (Static Assets & CSS)',
        'description': 'ملفات CSS المسؤولة عن المظهر الجمالي الموحد، دعم الاتجاه العربي RTL، والأنماط الداكنة وتجاوب الشاشات.',
        'files': []
    },
    'maintenance_cli': {
        'title': 'أدوات الصيانة، السكربتات والترحيل (Maintenance, CLI & Migrations)',
        'description': 'سكربتات فحص قواعد البيانات، إنشاء المسؤول الخارق (Superadmin)، الترقيعات التاريخية، وأدوات الاختبار.',
        'files': []
    },
    'vendored_media': {
        'title': 'المكتبات المضمنة وأصول الإنتاج الإعلامي (Vendored & Media Assets)',
        'description': 'حزمة Poppler لمعالجة ملفات PDF، وأصول الهوية البصرية والحملات الترويجية والإنتاج المرئي لمنصة LawSaaS.',
        'files': []
    }
}

# Scan repository
all_rel_paths = []
for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
    dirnames[:] = [d for d in dirnames if d not in {'.git', '__pycache__', '.pytest_cache', 'venv', 'node_modules'}]
    for f in filenames:
        rel = os.path.relpath(os.path.join(dirpath, f), ROOT_DIR).replace('\\', '/')
        all_rel_paths.append(rel)

print(f"Total files found across repository: {len(all_rel_paths)}")

# Metadata catalog dictionary
catalog = {}

for rel in all_rel_paths:
    full = os.path.join(ROOT_DIR, rel.replace('/', os.sep))
    size = os.path.getsize(full) if os.path.exists(full) else 0
    ext = os.path.splitext(rel)[1].lower()
    basename = os.path.basename(rel)
    dirname = os.path.dirname(rel) or '.'
    
    # Analyze Python files
    py_info = {'classes': [], 'functions': [], 'routes': [], 'imports': []}
    lines_count = 0
    if ext == '.py':
        try:
            with open(full, 'r', encoding='utf-8', errors='ignore') as fp:
                code = fp.read()
            lines_count = len(code.splitlines())
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    py_info['classes'].append(node.name)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    py_info['functions'].append(node.name)
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                            if dec.func.attr in ['get', 'post', 'put', 'delete', 'patch']:
                                p = dec.args[0].value if dec.args and isinstance(dec.args[0], ast.Constant) else ''
                                py_info['routes'].append(f"{dec.func.attr.upper()} {p}")
                elif isinstance(node, ast.Import):
                    for n in node.names:
                        py_info['imports'].append(n.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        py_info['imports'].append(node.module)
        except Exception as e:
            pass
    elif ext in ['.html', '.css', '.js', '.md', '.txt', '.yml', '.yaml', '.json', '.ini', '.bat', '.mako', '.sh']:
        try:
            with open(full, 'r', encoding='utf-8', errors='ignore') as fp:
                lines_count = len(fp.readlines())
        except:
            pass

    item = {
        'rel_path': rel,
        'basename': basename,
        'dirname': dirname,
        'ext': ext,
        'size': size,
        'lines': lines_count,
        'py_info': py_info
    }
    catalog[rel] = item

print(f"Catalog indexed {len(catalog)} files successfully.")

# Save catalog data to json
with open('catalog_summary.json', 'w', encoding='utf-8') as f:
    json.dump({k: {'size': v['size'], 'lines': v['lines'], 'classes': v['py_info']['classes'], 'functions': len(v['py_info']['functions']), 'routes': len(v['py_info']['routes'])} for k, v in catalog.items()}, f, ensure_ascii=False, indent=2)

print("Saved catalog_summary.json.")
