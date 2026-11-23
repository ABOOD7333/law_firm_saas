# -*- coding: utf-8 -*-
"""
LawSaaS Comprehensive Technical Blueprint Generator
Builds the complete HTML book and compiles it to PDF via Microsoft Edge Headless.
"""

import os
import sys
import subprocess
import json

ROOT = os.getcwd()

print("Building LawSaaS Technical Reference Book...")

# Load indexed catalog if available
catalog_data = {}
if os.path.exists('catalog_summary.json'):
    with open('catalog_summary.json', 'r', encoding='utf-8') as f:
        catalog_data = json.load(f)

# Helper for badges
def badge(text, b_type="info"):
    colors = {
        "core": ("#1e3a8a", "#dbeafe"),      # Blue
        "sec": ("#7f1d1d", "#fee2e2"),       # Red
        "db": ("#064e3b", "#d1fae5"),        # Green
        "router": ("#431407", "#ffedd5"),    # Orange/Amber
        "ai": ("#3b0764", "#f3e8ff"),        # Purple
        "ui": ("#134e4a", "#ccfbf1"),        # Teal
        "cfg": ("#374151", "#f3f4f6"),       # Gray
        "legacy": ("#831843", "#fce7f3"),    # Pink/Magenta
        "active": ("#065f46", "#d1fae5"),    # Emerald
        "unused": ("#991b1b", "#fee2e2"),    # Crimson
    }
    bg, fg = colors.get(b_type, ("#1e293b", "#f1f5f9"))
    return f'<span style="background-color:{fg}; color:{bg}; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; border: 1px solid {bg}33; display: inline-block; margin: 1px;">{text}</span>'

# HTML Header with print styling and Cairo/Tajawal fonts
html_parts = []

html_parts.append("""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>الخريطة التقنية الشاملة لمشروع LawSaaS</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&family=Tajawal:wght@400;500;700;800&family=Fira+Code:wght@400;500&display=swap');

        @page {
            size: A4 portrait;
            margin: 18mm 15mm 20mm 15mm;
            @bottom-center {
                content: counter(page);
                font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif;
                font-size: 9pt;
                color: #64748b;
            }
            @bottom-left {
                content: "المرجع التقني الشامل - LawSaaS";
                font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif;
                font-size: 8pt;
                color: #94a3b8;
            }
            @bottom-right {
                content: "شركة وزيرك للحلول السحابية (Waziruk)";
                font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif;
                font-size: 8pt;
                color: #94a3b8;
            }
        }

        *, *:before, *:after {
            box-sizing: border-box;
        }

        body {
            font-family: 'Cairo', 'Tajawal', 'Segoe UI', Tahoma, sans-serif;
            direction: rtl;
            text-align: right;
            background-color: #ffffff;
            color: #0f172a;
            font-size: 10.5pt;
            line-height: 1.65;
            margin: 0;
            padding: 0;
        }

        /* Cover Page */
        .cover-page {
            page-break-after: always;
            height: 100vh;
            min-height: 250mm;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 40px 20px;
            background: linear-gradient(135deg, #0b132b 0%, #1c2541 50%, #3a506b 100%);
            color: #ffffff;
            border-radius: 8px;
            box-shadow: inset 0 0 100px rgba(0,0,0,0.5);
            border: 3px solid #d4af37;
        }

        .cover-header {
            text-align: center;
            border-bottom: 2px solid rgba(212, 175, 55, 0.4);
            padding-bottom: 25px;
        }

        .cover-logo-badge {
            display: inline-block;
            background: rgba(212, 175, 55, 0.15);
            border: 2px solid #d4af37;
            color: #d4af37;
            padding: 8px 24px;
            border-radius: 30px;
            font-weight: 800;
            font-size: 14pt;
            letter-spacing: 1px;
            margin-bottom: 20px;
        }

        .cover-title {
            font-size: 26pt;
            font-weight: 900;
            color: #ffffff;
            margin: 10px 0;
            line-height: 1.3;
            text-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }

        .cover-subtitle {
            font-size: 14pt;
            font-weight: 600;
            color: #d4af37;
            margin: 10px 0 0 0;
            line-height: 1.5;
        }

        .cover-body {
            text-align: center;
            margin: 40px 0;
            background: rgba(255, 255, 255, 0.05);
            padding: 30px;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .cover-desc {
            font-size: 11.5pt;
            color: #e2e8f0;
            line-height: 1.8;
            max-width: 90%;
            margin: 0 auto;
        }

        .cover-meta {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 30px;
            border-top: 1px solid rgba(212, 175, 55, 0.3);
            padding-top: 20px;
            font-size: 10pt;
        }

        .cover-meta-item {
            text-align: center;
        }

        .cover-meta-label {
            color: #94a3b8;
            font-size: 8.5pt;
            display: block;
            margin-bottom: 4px;
        }

        .cover-meta-val {
            color: #ffffff;
            font-weight: 700;
        }

        .cover-footer {
            text-align: center;
            border-top: 2px solid rgba(212, 175, 55, 0.4);
            padding-top: 20px;
            font-size: 9pt;
            color: #94a3b8;
        }

        /* Typography & Layout */
        h1, h2, h3, h4 {
            font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif;
            color: #0f172a;
            font-weight: 800;
            margin-top: 24px;
            margin-bottom: 12px;
            line-height: 1.35;
        }

        h1 {
            font-size: 18pt;
            border-right: 5px solid #1e3a8a;
            padding-right: 12px;
            background: #f1f5f9;
            padding-top: 6px;
            padding-bottom: 6px;
            border-radius: 0 4px 4px 0;
            page-break-before: always;
        }

        h2 {
            font-size: 14pt;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 6px;
            color: #1e3a8a;
            margin-top: 22px;
        }

        h3 {
            font-size: 11.5pt;
            color: #334155;
            margin-top: 16px;
        }

        p {
            margin: 6px 0 10px 0;
            text-align: justify;
        }

        .lead-text {
            font-size: 11.5pt;
            font-weight: 600;
            color: #1e293b;
            background: #f8fafc;
            padding: 12px 16px;
            border-radius: 6px;
            border-right: 4px solid #3b82f6;
            margin-bottom: 15px;
        }

        /* Callout / Alert Boxes */
        .callout {
            padding: 12px 16px;
            border-radius: 6px;
            margin: 12px 0;
            font-size: 10pt;
            page-break-inside: avoid;
        }

        .callout-info {
            background-color: #eff6ff;
            border-right: 4px solid #3b82f6;
            color: #1e40af;
        }

        .callout-warning {
            background-color: #fffbeb;
            border-right: 4px solid #f59e0b;
            color: #92400e;
        }

        .callout-danger {
            background-color: #fef2f2;
            border-right: 4px solid #ef4444;
            color: #991b1b;
        }

        .callout-success {
            background-color: #f0fdf4;
            border-right: 4px solid #10b981;
            color: #065f46;
        }

        .callout-title {
            font-weight: 800;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        /* Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 14px 0 20px 0;
            font-size: 9.5pt;
            page-break-inside: auto;
        }

        tr {
            page-break-inside: avoid;
            page-break-after: auto;
        }

        thead {
            display: table-header-group;
        }

        th {
            background: #1e293b;
            color: #ffffff;
            font-weight: 700;
            padding: 8px 10px;
            border: 1px solid #334155;
            text-align: right;
            font-size: 9.5pt;
        }

        td {
            padding: 8px 10px;
            border: 1px solid #e2e8f0;
            vertical-align: top;
            line-height: 1.5;
        }

        tbody tr:nth-child(even) {
            background-color: #f8fafc;
        }

        tbody tr:hover {
            background-color: #f1f5f9;
        }

        /* Tree and Code Blocks */
        pre, code {
            font-family: 'Fira Code', 'Consolas', monospace;
            direction: ltr;
            text-align: left;
        }

        pre.tree-box {
            background: #0f172a;
            color: #38bdf8;
            padding: 16px;
            border-radius: 6px;
            font-size: 8.5pt;
            line-height: 1.45;
            overflow-x: hidden;
            border: 1px solid #1e293b;
            page-break-inside: avoid;
            margin: 14px 0;
        }

        code.inline-code {
            background: #f1f5f9;
            color: #0f172a;
            padding: 2px 5px;
            border-radius: 3px;
            font-size: 8.5pt;
            border: 1px solid #cbd5e1;
        }

        /* Flowchart / Workflow Cards */
        .workflow-container {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin: 16px 0;
            page-break-inside: avoid;
        }

        .workflow-step {
            display: flex;
            align-items: stretch;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }

        .step-num {
            background: #1e3a8a;
            color: #ffffff;
            font-weight: 800;
            font-size: 12pt;
            width: 45px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .step-content {
            padding: 10px 14px;
            flex-grow: 1;
        }

        .step-title {
            font-weight: 700;
            color: #0f172a;
            font-size: 10.5pt;
            margin-bottom: 3px;
        }

        .step-desc {
            font-size: 9pt;
            color: #475569;
            line-height: 1.45;
        }

        .step-files {
            margin-top: 6px;
            font-size: 8.5pt;
            color: #1e40af;
            font-family: monospace;
            direction: ltr;
            text-align: right;
        }

        .arrow-down {
            text-align: center;
            color: #64748b;
            font-size: 14pt;
            line-height: 1;
            margin: -4px 0;
        }

        /* Card Container */
        .card-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin: 14px 0;
            page-break-inside: avoid;
        }

        .feature-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 12px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            border-top: 3px solid #1e3a8a;
        }

        .feature-card-title {
            font-weight: 700;
            font-size: 10.5pt;
            color: #1e293b;
            margin-bottom: 6px;
        }

        .feature-card-desc {
            font-size: 9pt;
            color: #475569;
            line-height: 1.5;
        }

        /* Table of Contents */
        .toc-list {
            list-style: none;
            padding: 0;
            margin: 20px 0;
        }

        .toc-item {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            padding: 7px 0;
            border-bottom: 1px dotted #cbd5e1;
            font-size: 10.5pt;
        }

        .toc-title {
            font-weight: 600;
            color: #0f172a;
        }

        .toc-badge {
            color: #1e3a8a;
            font-weight: 700;
            font-size: 9.5pt;
        }

        .page-break {
            page-break-before: always;
        }

        .metric-banner {
            display: flex;
            justify-content: space-around;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            margin: 18px 0;
            text-align: center;
            page-break-inside: avoid;
        }

        .metric-box-val {
            font-size: 18pt;
            font-weight: 900;
            color: #1e3a8a;
            line-height: 1.2;
        }

        .metric-box-lbl {
            font-size: 8.5pt;
            color: #64748b;
            font-weight: 600;
            margin-top: 3px;
        }
    </style>
</head>
<body>
""")

# ==================== 1. COVER PAGE ====================
html_parts.append("""
<div class="cover-page">
    <div class="cover-header">
        <div class="cover-logo-badge">⚖️ LawSaaS Enterprise Edition 2.5</div>
        <div class="cover-title">الخريطة التقنية الشاملة لمشروع LawSaaS</div>
        <div class="cover-subtitle">الدليل المرجعي الكامل للمجلدات والملفات، الأكواد، البنية المعمارية، وتدفق البيانات</div>
    </div>

    <div class="cover-body">
        <div class="cover-desc">
            مرجع هندسي تفصيلي يوثق بالكامل النظام السحابي لإدارة مكاتب وشركات المحاماة (LawSaaS). يغطي هذا المرجع كل ملف ومجلد داخل المستودع، ويوضح وظيفته المحددة، محتوياته البرمجية، ارتباطاته، تصنيفه، وما قد يتأثر عند تعديله، مع توثيق شامل لنمط العزل متعدد المكاتب (Multi-Tenancy)، دورات تدفق البيانات، ومحاذير التعديل وحماية الإنتاج.
        </div>
        <div class="cover-meta">
            <div class="cover-meta-item">
                <span class="cover-meta-label">المستودع الرسمي</span>
                <span class="cover-meta-val">ABOOD7333 / law_firm_saas</span>
            </div>
            <div class="cover-meta-item">
                <span class="cover-meta-label">إصدار المرجع</span>
                <span class="cover-meta-val">v2.5 Enterprise (نوفمبر 2026)</span>
            </div>
            <div class="cover-meta-item">
                <span class="cover-meta-label">البيئة البرمجية</span>
                <span class="cover-meta-val">FastAPI + Jinja2 + SQLAlchemy</span>
            </div>
        </div>
    </div>

    <div class="cover-footer">
        <div>تم إعداد هذا المرجع التوثيقي بموجب فحص حي ومباشر للمستودع وكافة ملفاته التنفيذية</div>
        <div style="margin-top: 4px; font-weight: bold; color: #cbd5e1;">منصة وزيرك للحلول البرمجية القانونية — Waziruk Cloud Systems</div>
    </div>
</div>
""")

# ==================== 2. TABLE OF CONTENTS ====================
html_parts.append("""
<div class="page-break"></div>
<h1>فهرس المحتويات وخارطة الدليل المرجعي</h1>
<p class="lead-text">
صُمم هذا الدليل المرجعي ليكون رفيقك التقني الدائم؛ بحيث عندما تتصفح أي مجلد أو تفتح أي ملف في مستودع LawSaaS، تستطيع العودة لهذا الفهرس لمعرفة دور الملف الدقيق وموضعه في منظومة العمل دون أي تخمين.
</p>

<div class="metric-banner">
    <div>
        <div class="metric-box-val">815</div>
        <div class="metric-box-lbl">إجمالي ملفات المستودع</div>
    </div>
    <div>
        <div class="metric-box-val">224</div>
        <div class="metric-box-lbl">ملفات الأكواد والنواة والقوالب</div>
    </div>
    <div>
        <div class="metric-box-val">43</div>
        <div class="metric-box-lbl">راوتر ووحدة أعمال API</div>
    </div>
    <div>
        <div class="metric-box-val">54</div>
        <div class="metric-box-lbl">جدول ونموذج بيانات (ORM)</div>
    </div>
    <div>
        <div class="metric-box-val">73</div>
        <div class="metric-box-lbl">واجهة وقالب عرض Jinja2</div>
    </div>
</div>

<ul class="toc-list">
    <li class="toc-item">
        <span class="toc-title">المقدمة: رؤية المشروع والمعمارية العامة (Architecture Overview)</span>
        <span class="toc-badge">الفصل الأول</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">شجرة المجلدات الشاملة للمشروع وفلسفة التنظيم (Directory Tree)</span>
        <span class="toc-badge">الفصل الثاني</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">الدليل المرجعي لملفات الجذر الأساسية والإعدادات (Root Directory Files)</span>
        <span class="toc-badge">الفصل الثالث</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">الدليل المرجعي لنواة النظام ومركز الأمان (Core & Security Center)</span>
        <span class="toc-badge">الفصل الرابع</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">الدليل المرجعي لقاعدة البيانات والنماذج والتهجير (Database & Migrations)</span>
        <span class="toc-badge">الفصل الخامس</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">الدليل المرجعي لوحدات الأعمال ونقاط النهاية (Routers & Endpoints - 43 ملفاً)</span>
        <span class="toc-badge">الفصل السادس</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">الدليل المرجعي لمحركات الذكاء الاصطناعي والتوليد المعزز (AI & RAG Engines)</span>
        <span class="toc-badge">الفصل السابع</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">الدليل المرجعي لواجهات المستخدم وقوالب العرض (Frontend Templates - 73 قالباً)</span>
        <span class="toc-badge">الفصل الثامن</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">الدليل المرجعي لأدوات الصيانة، السكربتات والأصول المضمنة (Maintenance & Media)</span>
        <span class="toc-badge">الفصل التاسع</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">مخططات مسارات العمل وسير العمليات الحيوية (Operational Workflows)</span>
        <span class="toc-badge">الفصل العاشر</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">دليل الملفات الحساسة ومحاذير التعديل (Sensitive Files & Safety Guide)</span>
        <span class="toc-badge">الفصل الحادي عشر</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">تدقيق النظافة البرمجية: الملفات المكررة، القديمة، والمهملة (Codebase Hygiene)</span>
        <span class="toc-badge">الفصل الثاني عشر</span>
    </li>
    <li class="toc-item">
        <span class="toc-title">قاموس المصطلحات البرمجية والمعمارية (Technical Glossary)</span>
        <span class="toc-badge">الملحق المرجعي</span>
    </li>
</ul>
""")

# ==================== 3. CHAPTER 1: ARCHITECTURE ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل الأول: رؤية المشروع والمعمارية العامة (Architecture Overview)</h1>

<h2>1. ما هو مشروع LawSaaS؟</h2>
<p>
مشروع <strong>LawSaaS</strong> (المعروف تجارياً باسم <strong>وزيرك - Waziruk</strong>) هو منصة برمجية سحابية متكاملة كخدمة (SaaS) موجهة لإدارة مكاتب وشركات المحاماة والاستشارات القانونية، متوافقة بشكل متخصص مع الأنظمة والإجراءات القضائية في الجمهورية اليمنية والمملكة العربية السعودية، مع دعمه الكامل للفوترة الإلكترونية (ZATCA)، الذكاء الاصطناعي التوليدي القانوني، وبوابات خدمة الموكلين الذاتية، وتطبيقات الهاتف الذكي.
</p>

<h2>2. النمط المعماري للمشروع (Architectural Pattern)</h2>
<p>
يعتمد المشروع على نمط معمارية <strong>Monolith معياري متطور (Modular Monolith)</strong>، قائم على التقنيات الحديثة التالية:
</p>

<div class="card-grid">
    <div class="feature-card">
        <div class="feature-card-title">🚀 إطار العمل الخلفي (FastAPI - Python)</div>
        <div class="feature-card-desc">
            يوفر أداءً فائق السرعة عبر ASGI، ويدعم العمليات غير المتزامنة (Asynchronous)، مع التوثيق التلقائي لنقاط النهاية عبر OpenAPI (Swagger)، وتوليد استجابات هجينة (HTML للويب و JSON لتطبيق الموبايل وواجهات الـ REST).
        </div>
    </div>
    <div class="feature-card">
        <div class="feature-card-title">🗄️ محرك قواعد البيانات (SQLAlchemy ORM + Alembic)</div>
        <div class="feature-card-desc">
            طبقة تجريد متقدمة تدعم SQLite في التطوير المحلي و PostgreSQL في بيئة الإنتاج السحابية، مع إدارة العلاقات والمفاتيح الأجنبية وتتبع ترقيات المخططات بدقة عبر Alembic.
        </div>
    </div>
    <div class="feature-card">
        <div class="feature-card-title">🎨 واجهة المستخدم (Jinja2 SSR + Bootstrap + Tailwind)</div>
        <div class="feature-card-desc">
            توليد الواجهات على جانب الخادم (Server-Side Rendering) لسرعة التحميل وتوافق محركات البحث، مع دعم كامل للاتجاه العربي (RTL) وتنسيقات CSS مخصصة وتفاعلية عبر JavaScript Vanilla و Alpine.js.
        </div>
    </div>
    <div class="feature-card">
        <div class="feature-card-title">🛡️ معمارية العزل المتعدد (Multi-Tenancy with Office Isolation)</div>
        <div class="feature-card-desc">
            قاعدة بيانات مشتركة مع عزل منطقي صارم على مستوى الصفوف (Row-Level Tenancy Isolation) استناداً إلى معرف المكتب (<code>office_id</code>)، مدعومة بوسيطات تحقق (Middleware) ودوال حماية تمنع تسرب أي بيانات بين المكاتب نهائياً.
        </div>
    </div>
</div>

<h2>3. الفلسفة التشغيلية للربط بين المكونات</h2>
<div class="callout callout-info">
    <div class="callout-title">💡 كيف تترابط طبقات LawSaaS؟</div>
    <p>
        عند وصول أي طلب HTTP من المتصفح أو تطبيق الهاتف، يمر أولاً عبر <strong>وسيطات الأمان (Security Middleware)</strong> في <code>main.py</code> و <code>core/security_center/</code> للتحقق من العناوين ومنع الهجمات. ثم تستلم <strong>وحدة التوجيه المناسبة (Router)</strong> الطلب وتمرره إلى <strong>دوال التبعيات (dependencies.py)</strong> للتحقق من هوية المستخدم وصلاحياته ومكتبه. بعد ذلك، تستعلم الدوال من <strong>نماذج قاعدة البيانات (database/models.py)</strong>، وتُرجع النتيجة إما كواجهة مستخدم مُجهزة عبر <strong>قوالب Jinja2</strong> أو كبيانات JSON مشفرة للتطبيقات الخارجية.
    </p>
</div>
""")

# ==================== 4. CHAPTER 2: DIRECTORY TREE ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل الثاني: شجرة المجلدات وفلسفة التنظيم الهيكلي</h1>
<p class="lead-text">
يعتمد تنظيم مجلدات LawSaaS على الفصل الواضح بين المسؤوليات (Separation of Concerns). فيما يلي الشجرة الفعلية لكافة مجلدات المشروع:
</p>

<pre class="tree-box">
law_firm_saas/
│
├── .github/                      # إعدادات منصة GitHub وأتمتة خطوط التكامل والنشر المستمر
│   └── workflows/ci.yml          # سير عمل GitHub Actions للفحص الآلي والاختبارات
│
├── core/                         # نواة النظام الأمنية والخدمات المنطقية المشتركة
│   ├── security_center/          # مركز الأمان السيبراني المتكامل ومراقبة الهجمات والتشفير
│   ├── audit.py                  # تسجيل تدقيق العمليات الحساسة في النظام
│   ├── conflict_checker.py       # محرك فحص تضارب المصالح بين الموكلين والخصوم
│   ├── error_handler.py          # معالجات الأخطاء الموحدة
│   ├── rate_limiter.py           # حماية النظام من الهجمات التكرارية والفيضية
│   ├── security.py               # دوال التشفير، التجزئة، وتوليد الرموز السرية
│   ├── subscription_tiers.py     # منطق باقات الاشتراك وحدود الموارد المخصصة لكل مكتب
│   ├── upload_security.py        # فحص الملفات المرفوعة والتحقق من تواقيعها السحرية
│   ├── workflow_engine.py        # محرك أتمتة الإجراءات والمهام التلقائية
│   └── yemeni_laws.py            # مرجع النصوص والمواد القانونية اليمنية
│
├── database/                     # طبقة قاعدة البيانات، النماذج، والاتصال
│   ├── database.py               # إنشاء المحرك، إدارة جلسات العمل، والترقية التلقائية
│   ├── models.py                 # الـ 54 نموذجاً الأساسياً (الجداول، العلاقات، الحقول)
│   └── security_models.py        # 9 نماذج خاصة بمركز الأمان السيبراني
│
├── alembic/                      # أداة الترحيل وإدارة ترقيات مخططات قاعدة البيانات
│   ├── versions/                 # ملفات إصدارات الترقية المؤرخة
│   └── env.py                    # إعدادات اتصال وتوافق Alembic مع نماذج التطبيق
│
├── routers/                      # 43 وحدة توجيه برمجية تغطي جميع أقسام النظام
│   ├── accounting.py             # الفواتير، بنودها، سندات القبض، وباركود زاتكا
│   ├── incoming_cases.py         # القضايا الواردة، وقيد ورفع الدعاوى الجديدة (Section 0)
│   ├── mobile_api.py             # الـ 44 نقطة نهاية الخاصة بتطبيق الهواتف الذكية
│   ├── reports_route.py          # محرك توليد التقارير القانونية والمالية بصيغة PDF
│   ├── documents_route.py        # إدارة المستندات، الإصدارات، والأرشفة
│   ├── ai_assistant.py           # المساعد القانوني الذكي القائم على الذكاء الاصطناعي
│   ├── client_portal.py          # بوابة الموكل الذاتية لمتابعة قضاياه وعقوده وفواتيره
│   ├── security_center.py        # واجهات وإعدادات مركز الأمان ومراقبة النظام
│   └── ... (35 راوتراً إضافياً تغطي الجلسات، الأحكام، المرافعات، الوكالات، الخ)
│
├── ai_engine/                    # محرك الذكاء الاصطناعي المباشر (Direct LLM Engine)
│   ├── knowledge_base/           # المعارف القانونية اليمنية، صياغة المذكرات، والإجراءات
│   ├── llm_service.py            # التخاطب مع Google Gemini API وضبط البرومبت
│   ├── intent_detector.py        # تصنيف استفسار المحامي وتحديد نيته البرمجية
│   ├── db_query_engine.py        # تحويل لغة المحامي الطبيعية إلى استعلامات قاعدة بيانات
│   └── search_engine.py          # البحث الدلالي في السجلات والقضايا
│
├── rag_engine/                   # محرك التوليد المعزز بالاسترجاع (Retrieval-Augmented Gen)
│   ├── core/                     # تقطيع النصوص (Chunking)، التضمين (Embedding)، والمتجهات
│   ├── loaders/                  # استخراج نصوص الـ PDF ومحرك التعرف الضوئي (OCR)
│   └── services/                 # تلخيص المستندات، تحليل العقود، وصياغة الردود
│
├── templates/                    # 73 قالب HTML مبنية بمحرك Jinja2
│   ├── accounting/               # قوالب الفواتير، عروض الأسعار، ونماذج السداد
│   ├── client_portal/            # واجهات بوابة الموكل (القضايا، العقود، التوقيع الرقمي)
│   ├── incoming_cases/           # قوالب القضايا الواردة ورفع الدعاوى التفاعلي
│   ├── intake/                   # نماذج استقطاب العملاء وتوقيع الاتفاقيات الرقمية
│   ├── kanban/                   # لوحة متابعة سير القضايا بنمط كانبان (Kanban Board)
│   └── components/               # الترويسات الرسمية والعناصر القابلة لإعادة الاستخدام
│
├── static/css/                   # ملفات التنسيق البصري (dashboard.css, style.css)
│
├── poppler/                      # حزمة برمجية مضمنة للتعامل مع ملفات PDF واستخراج نصوصها
│
└── LawSaaS_Media_Production/     # أصول الهوية البصرية، الفيديوهات الترويجية، ومخططات الإنتاج
</pre>

<h2>شرح وظيفة وفلسفة كل مجلد:</h2>
<table>
    <thead>
        <tr>
            <th style="width: 20%;">المجلد</th>
            <th style="width: 25%;">نوع الملفات</th>
            <th style="width: 55%;">الوظيفة وفلسفة التنظيم</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>جذر المشروع (Root)</strong></td>
            <td>Python, YAML, Docker, Config</td>
            <td>يحتوي على نقطة انطلاق الخادم (<code>main.py</code>)، التبعيات المشتركة (<code>dependencies.py</code>)، ملفات البيئة والحاويات (Docker)، ومتطلبات التشغيل. وُضعت هنا لتكون واضحة لأدوات النشر والاستضافة.</td>
        </tr>
        <tr>
            <td><strong>core/</strong></td>
            <td>Python Core Modules</td>
            <td>يضم منطق الأعمال المحايد المشترك الذي لا يرتبط براوتر معين؛ مثل التشفير، الصلاحيات، التدقيق، كشف تضارب المصالح، وفحص الفيروسات. يعزز مبدأ إعادة الاستخدام ومنع التكرار.</td>
        </tr>
        <tr>
            <td><strong>database/</strong></td>
            <td>SQLAlchemy Models & DB Config</td>
            <td>عزل طبقة البيانات ومخططات الجداول عن منطق الواجهات ونقاط النهاية، مما يتيح التعديل على الجداول والترحيل التلقائي دون المساس ببقية التطبيق.</td>
        </tr>
        <tr>
            <td><strong>routers/</strong></td>
            <td>FastAPI Routers</td>
            <td>تنظيم نقاط النهاية (Endpoints) وفق مجالات الأعمال القانونية (Domain-Driven)، بحيث يستقل كل قطاع (القضايا، المحاسبة، الجلسات، الموكلين) في ملف منفصل يسهل صيانته واختباره.</td>
        </tr>
        <tr>
            <td><strong>ai_engine/ & rag_engine/</strong></td>
            <td>AI & NLP & Vector Services</td>
            <td>فصل محركات الذكاء الاصطناعي والتوليد المعزز عن الراوترات التقليدية لتسهيل استبدال أو ترقية نماذج الذكاء الاصطناعي (مثل Gemini) دون التأثير على عمل النظام الأساسي.</td>
        </tr>
        <tr>
            <td><strong>templates/ & static/</strong></td>
            <td>Jinja2 HTML, CSS, JavaScript</td>
            <td>طبقة العرض والواجهات للمستخدم، مقسمة إلى مجلدات فرعية تعكس نفس تقسيم الراوترات لضمان التناغم التام وسهولة تعقب مسار كل صفحة.</td>
        </tr>
    </tbody>
</table>
""")

# ==================== 5. CHAPTER 3: ROOT FILES ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل الثالث: الدليل المرجعي لملفات الجذر الأساسية والإعدادات</h1>
<p class="lead-text">
ملفات الجذر هي الركائز الأساسية التي تنطلق منها خوادم المنصة وتُدار عبرها متغيرات البيئة والحاويات. فيما يلي جدول تفصيلي لكل ملف في جذر المستودع:
</p>

<table>
    <thead>
        <tr>
            <th style="width: 15%;">اسم الملف</th>
            <th style="width: 12%;">النوع والتصنيف</th>
            <th style="width: 28%;">الوظيفة الأساسية</th>
            <th style="width: 25%;">الارتباطات والتبعيات</th>
            <th style="width: 20%;">الأثر ومحاذير التعديل</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>main.py</strong><br><small>4,437 سطر</small></td>
            <td>""" + badge("Python", "core") + "<br>" + badge("أساسي وحرج", "sec") + """</td>
            <td>نقطة الدخول والانطلاق الرئيسية للتطبيق (App Entrypoint). ينشئ تطبيق FastAPI، يدمج كافة الوسيطات (CORS, Sessions, Security Headers)، يسجل الـ 37 راوتراً، ويحتوي على مسارات تسجيل الدخول ولوحة التحكم الرئيسية.</td>
            <td>يستورد <code>database/models.py</code>, <code>dependencies.py</code>, وجميع ملفات <code>routers/*</code>.</td>
            <td><strong style="color:#b91c1c;">خطر فائق:</strong> أي خطأ تركيبي هنا يوقف الخادم بأكمله عن العمل فوراً. يجب عدم تعديله إلا لإضافة وسيطة أو تسجيل راوتر جديد.</td>
        </tr>
        <tr>
            <td><strong>dependencies.py</strong><br><small>341 سطر</small></td>
            <td>""" + badge("Python", "core") + "<br>" + badge("أساسي وحرج", "sec") + """</td>
            <td>وحدة التبعيات المركزية (Dependency Injection). توفر دوال استخراج المستخدم الحالي <code>get_current_user</code>، فحص الجلسات في قاعدة البيانات، التحقق من الصلاحيات <code>check_user_permission</code>، وتغليف محرك القوالب <code>templates</code> لمنع الحلقات الدائرية (Circular Imports).</td>
            <td>يستورد <code>database/database.py</code>, <code>database/models.py</code>, <code>core/security.py</code>. يُستورد من قِبل جميع ملفات <code>routers/*</code>.</td>
            <td><strong style="color:#b91c1c;">خطر فائق:</strong> التعديل غير المنضبط هنا يعطل تسجيل الدخول وصلاحيات الوصول لكافة مستخدمي المنصة بلا استثناء.</td>
        </tr>
        <tr>
            <td><strong>database.py</strong> (في الجذر)<br><small>28,146 بايت</small></td>
            <td>""" + badge("Python", "legacy") + "<br>" + badge("مكرر قديم", "unused") + """</td>
            <td>نسخة قديمة وتاريخية من ملف اتصال قاعدة البيانات كانت مستخدمة قبل تنظيم المشروع في حزم فرعية. حلت محله الحزمة الرسمية <code>database/database.py</code>.</td>
            <td>غير مستورد في <code>main.py</code> أو الراوترات الحديثة (تستورد من <code>database.database</code>).</td>
            <td><strong style="color:#b45309;">حذر:</strong> لا يجب التعديل عليه لأنه مهمل، وتعديله لا يؤثر على النظام الفعلي، ويُفضل أرشفته لاحقاً.</td>
        </tr>
        <tr>
            <td><strong>email_service.py</strong><br><small>14,269 بايت</small></td>
            <td>""" + badge("Python", "core") + "<br>" + badge("خدمي مساعد", "active") + """</td>
            <td>خدمة إرسال رسائل البريد الإلكتروني (SMTP / SendGrid). ترسل إشعارات الجلسات، رموز التحقق OTP، تنبيهات المهام، وفواتير الموكلين مع قوالب HTML منسقة.</td>
            <td>يُستدعى من <code>main.py</code> (أثناء استعادة كلمة المرور والتسجيل)، ومن راوترات المهام والجلسات.</td>
            <td>تعديل إعدادات SMTP الخاطئة يؤدي لفشل وصول رسائل التفعيل ورموز الـ OTP للمستخدمين.</td>
        </tr>
        <tr>
            <td><strong>error_handler.py</strong> (في الجذر)<br><small>14,020 بايت</small></td>
            <td>""" + badge("Python", "core") + "<br>" + badge("مكرر مطابق", "active") + """</td>
            <td>معالج الأخطاء العام؛ متطابق تماماً في المحتوى مع <code>core/error_handler.py</code>. يوجه أخطاء 404 و 500 إلى صفحات خطأ احترافية بدلاً من شاشات الأعطال البرمجية.</td>
            <td>تستورده بعض السكربتات المباشرة، بينما تستورد النواة من مسار <code>core.error_handler</code>.</td>
            <td>تعديله قد يغير طريقة عرض وتنسيق شاشات الخطأ للمستخدمين.</td>
        </tr>
        <tr>
            <td><strong>Dockerfile</strong><br><small>1,881 بايت</small></td>
            <td>""" + badge("Docker", "cfg") + "<br>" + badge("أساسي للنشر", "core") + """</td>
            <td>ملف بناء الحاوية السحابية (Container Image). يثبت بيئة Python 3.12، المكتبات الاعتمادية، حزم تشغيل OCR، Poppler، ومكتبة Tesseract، ويضبط تشغيل Uvicorn.</td>
            <td>يُستخدم بواسطة <code>docker-compose.yml</code> ومستودع GitHub Actions أثناء بناء النشر السحابي.</td>
            <td>أي تعديل غير سليم يمنع بناء الحاوية السحابية على خادم الإنتاج ويفشل عمليات النشر.</td>
        </tr>
        <tr>
            <td><strong>docker-compose.yml</strong><br><small>2,171 بايت</small></td>
            <td>""" + badge("YAML", "cfg") + "<br>" + badge("أساسي للتشغيل", "core") + """</td>
            <td>ملف أوركسترا وتشغيل الحاويات؛ يعرف حاوية التطبيق <code>lawsaas_app</code>، وحاوية قاعدة البيانات PostgreSQL، والشبكات الافتراضية، ومجلدات التخزين المستدامة (Volumes).</td>
            <td>يتصل بـ <code>Dockerfile</code> وقاعدة البيانات ويقرأ المتغيرات من ملف <code>.env</code>.</td>
            <td>تعديل المنافذ أو المسارات هنا يغير طريقة تشغيل الخادم على VPS أو السحابة.</td>
        </tr>
        <tr>
            <td><strong>requirements.txt</strong><br><small>1,335 بايت</small></td>
            <td>""" + badge("Text", "cfg") + "<br>" + badge("قائمة الاعتماديات", "core") + """</td>
            <td>يحدد كافة مكتبات بايثون المطلوبة لإطلاق التطبيق (FastAPI, Uvicorn, SQLAlchemy, Pydantic, ReportLab, Jinja2, وغيرها) مع أرقام إصداراتها المعتمدة.</td>
            <td>يُقرأ من قِبل <code>Dockerfile</code> وأداة التثبيت <code>pip</code>.</td>
            <td>إضافة أو حذف مكتبات بدون اختبار قد يحدث تعارضاً في إصدارات حزم بايثون.</td>
        </tr>
        <tr>
            <td><strong>alembic.ini</strong><br><small>1,121 بايت</small></td>
            <td>""" + badge("Config", "cfg") + "<br>" + badge("إعدادات التهجير", "db") + """</td>
            <td>ملف تهيئة أداة Alembic لإدارة ترقيات وتعديلات قاعدة البيانات، وتوجيه مسارات ملفات التهجير وقوالب السكربتات.</td>
            <td>يرتبط بمجلد <code>alembic/</code> ومسار قاعدة البيانات المعرف في متغيرات البيئة.</td>
            <td>الخطأ في رابط قاعدة البيانات يعطل توليد وتطبيق ترقيات الجداول البرمجية.</td>
        </tr>
        <tr>
            <td><strong>.env.example</strong><br><small>1,253 بايت</small></td>
            <td>""" + badge("Config", "cfg") + "<br>" + badge("قالب الإعدادات", "sec") + """</td>
            <td>قالب مرجعي لمتغيرات البيئة الحساسة (Database URL, Secret Key, Gemini API Key, SMTP, ZATCA Settings) الخالي من البيانات السرية ليسترشد به المطورون.</td>
            <td>يُنسخ إلى <code>.env</code> الحقيقي عند تنصيب المشروع في أي بيئة عمل جديدة.</td>
            <td>لا يحتوي على أسرار؛ ويجب تحديثه كلما أضيفت خدمة جديدة تحتاج مفاتيح وصول.</td>
        </tr>
    </tbody>
</table>
""")

# ==================== 6. CHAPTER 4: CORE & SECURITY CENTER ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل الرابع: الدليل المرجعي لنواة النظام ومركز الأمان (Core & Security)</h1>
<p class="lead-text">
يمثل مجلد <code>core/</code> القلب الحصين لنظام LawSaaS؛ حيث تنفصل فيه المعالجات الأمنية والمحركات التشغيلية عن طبقات العرض والراوترات لضمان أعلى معايير الحماية والتنظيم.
</p>

<h2>1. ملفات النواة العامة (core/)</h2>
<table>
    <thead>
        <tr>
            <th style="width: 20%;">اسم الملف</th>
            <th style="width: 35%;">الوظيفة الأساسية</th>
            <th style="width: 25%;">الارتباطات والتبعيات</th>
            <th style="width: 20%;">الحالة والأهمية</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>core/audit.py</strong><br><small>2,470 بايت</small></td>
            <td>تسجيل كافة العمليات الحساسة التي يجريها المحامون والموظفون (إنشاء قضية، تعديل حكم، حذف مستند، سداد فاتورة) مع تسجيل الـ IP، المستخدم، والوقت الدقيق.</td>
            <td>يستورد <code>database/models.py</code> (جدول <code>LawAuditLog</code>) ويُستدعى في الراوترات الحساسة.</td>
            <td>""" + badge("أساسي ونشط", "active") + """</td>
        </tr>
        <tr>
            <td><strong>core/conflict_checker.py</strong><br><small>13,361 بايت</small></td>
            <td>محرك خوارزمي متقدم لكشف <strong>تضارب المصالح</strong> القانوني؛ يفحص بالذكاء الاصطناعي والبحث الصوتي والنصي أسماء الخصوم وأرقام هوياتهم والشركات عبر كافة القضايا السابقة.</td>
            <td>يستورد <code>database/models.py</code> (قضايا، أطراف، موكلين) ويُستدعى في راوتر <code>conflict_check.py</code>.</td>
            <td>""" + badge("أساسي ومحوري", "active") + """</td>
        </tr>
        <tr>
            <td><strong>core/error_handler.py</strong><br><small>14,020 بايت</small></td>
            <td>المعالج المعتمد للأخطاء والاستثناءات غير المتوقعة (Database errors, Validation errors) لمنع تسريب أي Traceback أو أسرار تقنية للمستخدمين واستبدالها برسائل ودية.</td>
            <td>يُسجل في <code>main.py</code> لمعالجة استثناءات خادم FastAPI بالكامل.</td>
            <td>""" + badge("حرج وأساسي", "sec") + """</td>
        </tr>
        <tr>
            <td><strong>core/logger.py</strong><br><small>2,561 بايت</small></td>
            <td>نظام التسجيل المركزي المتطور (Centralized Logging)؛ يدير دوران السجلات (Log Rotation) وتسجيل الأحداث في ملفات يومية مع تنسيق قياسي يسهل تحليله.</td>
            <td>يُستخدم في كافة أنحاء التطبيق عبر استدعاء مسجل الأحداث <code>logger</code>.</td>
            <td>""" + badge("خدمي أساسي", "active") + """</td>
        </tr>
        <tr>
            <td><strong>core/rate_limiter.py</strong><br><small>4,212 بايت</small></td>
            <td>محدد معدل الطلبات (Rate Limiting)؛ يمنع هجمات التخمين على كلمات المرور (Brute Force) وهجمات حجب الخدمة عبر تقييد عدد الطلبات المسموح بها لكل IP ودقيقة.</td>
            <td>يُطبق كـ Dependency على مسارات تسجيل الدخول، استعادة كلمة المرور، ونقاط الـ API.</td>
            <td>""" + badge("حرج أمنياً", "sec") + """</td>
        </tr>
        <tr>
            <td><strong>core/security.py</strong><br><small>4,418 بايت</small></td>
            <td>ترسانة التشفير والأمان؛ تشفير كلمات المرور عبر <code>bcrypt</code>، توليد والتحقق من رموز الجلسات السرية، تجزئة الرموز برمجياً، وفك تشفير الرموز الآمنة.</td>
            <td>تستورده <code>dependencies.py</code> و <code>main.py</code> وجميع راوترات التحقق.</td>
            <td>""" + badge("فائق الحساسية", "sec") + """</td>
        </tr>
        <tr>
            <td><strong>core/subscription_tiers.py</strong><br><small>10,438 بايت</small></td>
            <td>منطق تسعير وباقات الاشتراك في منصة LawSaaS (مجانية، أساسية، احترافية، مؤسسات) والتحقق من سعة المكتب (عدد القضايا المسموح به، مساحة التخزين، والمستخدمين).</td>
            <td>يُستدعى في راوترات إضافة القضايا والمستخدمين لفرض حدود الباقة على المكاتب.</td>
            <td>""" + badge("تجاري وتشغيلي", "active") + """</td>
        </tr>
        <tr>
            <td><strong>core/upload_security.py</strong><br><small>2,648 بايت</small></td>
            <td>حارس الملفات المرفوعة؛ يتحقق من الامتدادات المسموح بها، يفحص التواقيع السحرية للملفات (Magic Bytes)، ويمنع هجمات حقن الملفات التنفيذية أو تخطي المسارات (Path Traversal).</td>
            <td>يُستدعى في <code>documents_route.py</code> وكافة معالجات رفع الوثائق.</td>
            <td>""" + badge("حرج أمنياً", "sec") + """</td>
        </tr>
        <tr>
            <td><strong>core/workflow_engine.py</strong><br><small>10,310 بايت</small></td>
            <td>محرك أتمتة الإجراءات (Trigger-Action Engine)؛ يقوم تلقائياً بإنشاء مهام تذكيرية فور قيد جلسة جديدة، أو إرسال إشعار للموكل عند صدور حكم، وفق قواعد سير العمل.</td>
            <td>يتعامل مع جداول <code>LawWorkflowRules</code> و <code>LawTasks</code> و <code>LawHearings</code>.</td>
            <td>""" + badge("تشغيلي متقدم", "active") + """</td>
        </tr>
        <tr>
            <td><strong>core/yemeni_laws.py</strong><br><small>3,828 بايت</small></td>
            <td>محرك النصوص التشريعية والقانونية المعتمدة في اليمن (قانون الإجراءات الجزائية، المرافعات المدنية، الإثبات، وقانون الشركات) لتغذية محركات البحث والاستشارات.</td>
            <td>يرتبط بـ <code>ai_engine/</code> وراوتر <code>yemeni_laws.py</code>.</td>
            <td>""" + badge("معرفي قانوني", "active") + """</td>
        </tr>
    </tbody>
</table>

<h2>2. منظومة مركز الأمان السيبراني المتكامل (core/security_center/)</h2>
<table>
    <thead>
        <tr>
            <th style="width: 25%;">اسم الملف</th>
            <th style="width: 50%;">الوظيفة والمسؤولية</th>
            <th style="width: 25%;">التأثير ومستوى الأهمية</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>alert_service.py</strong></td>
            <td>إرسال تنبيهات الأمان الفورية لمديري النظام عبر البريد الإلكتروني عند اكتشاف أي اختراق أو هجوم.</td>
            <td>""" + badge("أمان سيبراني", "sec") + """</td>
        </tr>
        <tr>
            <td><strong>audit_chain.py</strong></td>
            <td>سلسلة التدقيق غير القابلة للتلاعب (Immutable Audit Chain)؛ تربط سجلات العمليات بسلسلة كتلية تجزيئية (Hash-Chain) لاكتشاف أي تعديل مباشر في قاعدة البيانات.</td>
            <td>""" + badge("أمان وحوكمة", "sec") + """</td>
        </tr>
        <tr>
            <td><strong>crypto_fields.py</strong></td>
            <td>تشفير الحقول الحساسة في قاعدة البيانات (مثل الأرقام الوطنية للموكلين، الحسابات البنكية) بتشفير AES-256-GCM.</td>
            <td>""" + badge("فائق الحساسية", "sec") + """</td>
        </tr>
        <tr>
            <td><strong>file_scanner.py</strong></td>
            <td>فاحص الفيروسات المباشر؛ يتصل بخدمة ClamAV ويفحص الملفات المرفوعة بحثاً عن برمجيات خبيثة أو سكربتات مدفونة.</td>
            <td>""" + badge("حماية الخادم", "sec") + """</td>
        </tr>
        <tr>
            <td><strong>monitor_middleware.py</strong></td>
            <td>وسيطة الحماية الاستباقية؛ تعترض كافة طلبات HTTP وتفحص المتغيرات لاكتشاف محاولات SQL Injection و XSS قبل وصولها للتطبيق.</td>
            <td>""" + badge("حائط صد حرج", "sec") + """</td>
        </tr>
        <tr>
            <td><strong>remediation_engine.py</strong></td>
            <td>محرك المعالجة التلقائية للهجمات؛ حظر عناوين الـ IP المهاجمة تلقائياً، وإغلاق الجلسات المشبوهة فوراً.</td>
            <td>""" + badge("دفاعي استباقي", "sec") + """</td>
        </tr>
        <tr>
            <td><strong>scanner_engine.py</strong></td>
            <td>محرك الفحص الدوري الشامل؛ يفحص إعدادات السيرفر، المنافذ المفتوحة، ومكتبات النظام لكشف الثغرات الأمنية المعروفة.</td>
            <td>""" + badge("تقييم مخاطر", "sec") + """</td>
        </tr>
        <tr>
            <td><strong>watchdog.py</strong></td>
            <td>كلب الحراسة البرمجي؛ يراقب استهلاك موارد الخادم واستقرار النظام ويبعث إشارات حيوية تفيد بسلامة الخدمات.</td>
            <td>""" + badge("مراقبة مستمرة", "sec") + """</td>
        </tr>
    </tbody>
</table>
""")

# ==================== 7. CHAPTER 5: DATABASE & MIGRATIONS ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل الخامس: الدليل المرجعي لقواعد البيانات، النماذج والتهجير</h1>
<p class="lead-text">
تعتمد منصة LawSaaS على نموذج بيانات علائقي ضخم يضم <strong>54 جدولاً أساسياً</strong> في <code>database/models.py</code> بالإضافة إلى <strong>9 جداول للأمان السيبراني</strong> في <code>database/security_models.py</code>. تم تصميم هذا المخطط ليعزل المكاتب بشكل صارم عبر حقل <code>office_id</code> الموجود في كافة الجداول التشغيلية.
</p>

<h2>1. ملفات طبقة قواعد البيانات</h2>
<table>
    <thead>
        <tr>
            <th style="width: 25%;">الملف والمسار</th>
            <th style="width: 15%;">الحجم</th>
            <th style="width: 40%;">الوظيفة والمحتويات</th>
            <th style="width: 20%;">الأثر عند التعديل</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>database/database.py</strong></td>
            <td>28,475 بايت</td>
            <td>ينشئ محرك SQLAlchemy Engine، يدير مجمع الاتصالات (Connection Pool)، ويوفر الدالة المركزية <code>get_db()</code> لحقن جلسات العمل. يحتوي أيضاً على <strong>محرك الترقية التلقائية (Auto-Migration Engine)</strong> الذي يضيف الأعمدة الناقصة تلقائياً في SQLite و PostgreSQL عند إطلاق التحديثات.</td>
            <td><strong style="color:#b91c1c;">حرج للغاية:</strong> أي خطأ يعطل اتصال التطبيق بقاعدة البيانات بالكامل.</td>
        </tr>
        <tr>
            <td><strong>database/models.py</strong></td>
            <td>82,104 بايت</td>
            <td>يحتوي على كافة نماذج الجداول الـ 54 والعلاقات (Relationships, Foreign Keys, Indexes, Cascades) لكافة كيانات النظام (مكاتب، موكلين، قضايا، جلسات، وثائق، فواتير، دعاوى واردة).</td>
            <td><strong style="color:#b91c1c;">حرج للغاية:</strong> تغيير أسماء الأعمدة أو أنواعها هنا دون ترحيل يتسبب في انهيار استعلامات SQL وفشل النظام.</td>
        </tr>
        <tr>
            <td><strong>database/security_models.py</strong></td>
            <td>13,862 بايت</td>
            <td>يحدد الجداول الـ 9 الخاصة بمركز الأمان (فحوصات الأمان، نتائج التدقيق، سجلات التنبيهات، والاعتماديات المشبوهة).</td>
            <td>يؤثر حصراً على عمل ومراقبة مركز الأمان السيبراني.</td>
        </tr>
        <tr>
            <td><strong>alembic/env.py</strong></td>
            <td>2,933 بايت</td>
            <td>يربط بيئة Alembic مع كائن <code>Base.metadata</code> لتتبع الفروقات التلقائية وتوليد ملفات ترقية المخطط البرمجية.</td>
            <td>تعديله مطلوب فقط عند تغيير استراتيجيات الترحيل أو الاتصال بقواعد بيانات جديدة.</td>
        </tr>
    </tbody>
</table>

<h2>2. خريطة الجداول الـ 54 في قاعدة البيانات (database/models.py)</h2>
<table>
    <thead>
        <tr>
            <th style="width: 20%;">القطاع الوظيفي</th>
            <th style="width: 35%;">الجداول والنماذج الأساسية</th>
            <th style="width: 45%;">البيانات المخزنة والعلاقات</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>الهوية والمصادقة والمكاتب</strong></td>
            <td><code>LawOffices</code><br><code>AccessProfiles</code><br><code>AuthSessions</code><br><code>AuthOtpTokens</code><br><code>PendingRegistrations</code></td>
            <td>بيانات مكاتب المحاماة المشتركة في الـ SaaS، حسابات المستخدمين وكلمات مرورهم المشفرة، جلسات الدخول الفعالة مع عناوين الـ IP، رموز التحقق OTP، وطلبات التسجيل المعلقة.</td>
        </tr>
        <tr>
            <td><strong>الموكلين والخصوم والوكالات</strong></td>
            <td><code>LawClients</code><br><code>LawClientRepresentatives</code><br><code>LawParties</code><br><code>LawPowerOfAttorney</code></td>
            <td>سجلات الموكلين، ممثليهم القانونيين، أطراف الدعاوى والخصوم (الأفراد والشركات)، والوكالات الشرعية والقانونية الصادرة لصالح المحامين مع تواريخ صلاحيتها.</td>
        </tr>
        <tr>
            <td><strong>القضايا والجلسات والمرافعات</strong></td>
            <td><code>LawCases</code><br><code>LawHearings</code><br><code>LawPleadings</code><br><code>LawJudgments</code><br><code>LawExecutions</code></td>
            <td>ملفات القضايا الكاملة، جدول جلسات المحاكم ومحاضرها، المذكرات واللوائح الجوابية والمرافعات المكتوبة، منطوق الأحكام القضائية الصادرة، وإجراءات التنفيذ الجبري.</td>
        </tr>
        <tr>
            <td><strong>الدعاوى الواردة والقيد الجديد</strong></td>
            <td><code>LawIncomingCases</code></td>
            <td>جدول القضايا والدعاوى الواردة (Section 0 إلى 6)، يخزن بيانات رفع الدعاوى الجديدة للشرطة، النيابة، المحاكم، والتنفيذ، مع المبالغ والطلبات والأسانيد.</td>
        </tr>
        <tr>
            <td><strong>المستندات والأرشيف والنسخ</strong></td>
            <td><code>LawDocuments</code><br><code>LawDocumentVersions</code><br><code>LawDeletedRecordArchive</code></td>
            <td>مسارات المستندات والملفات المرفوعة، تاريخ وتتبع إصدارات العقود والمذكرات، وسجل الأرشيف للحذف الآمن (Soft Delete).</td>
        </tr>
        <tr>
            <td><strong>المحاسبة والفوترة والأمانات</strong></td>
            <td><code>Invoices</code><br><code>InvoiceItems</code><br><code>ClientPayments</code><br><code>LawTrustAccounts</code><br><code>LawTrustTransactions</code></td>
            <td>الفواتير الضريبية والرسمية الصادرة للموكلين، بنودها، سندات القبض والدفع، وحسابات أمانات الموكلين (Trust Accounts) وحركاتها المالية المنفصلة.</td>
        </tr>
        <tr>
            <td><strong>المهام والمواعيد والتقادم</strong></td>
            <td><code>LawTasks</code><br><code>LawTimesheets</code><br><code>LawExpenses</code><br><code>LawLimitations</code></td>
            <td>المهام الإدارية والقانونية لفريق العمل، جداول تتبع ساعات العمل بالساعة، المصروفات القضائية، وحساب مدد ومواعيد السقوط والتقادم القانوني.</td>
        </tr>
        <tr>
            <td><strong>استقطاب العملاء والعقود</strong></td>
            <td><code>ClientIntakeForms</code><br><code>IntakeSubmissions</code><br><code>RetainerAgreements</code></td>
            <td>نماذج استقطاب الموكلين عبر الروابط العامة، الطلبات المرسلة من الجمهور، واتفاقيات الأتعاب الموقعة إلكترونياً (E-Signature).</td>
        </tr>
    </tbody>
</table>
""")

# ==================== 8. CHAPTER 6: ROUTERS & ENDPOINTS ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل السادس: الدليل المرجعي لوحدات الأعمال ونقاط النهاية (Routers - 43 ملفاً)</h1>
<p class="lead-text">
تمثل مجلد <code>routers/</code> العصب التنفيذي لكافة وظائف LawSaaS؛ حيث يحتوي على <strong>43 ملف راوتر</strong> مستقل، كل منها يعالج قطاعاً قانونياً أو إدارياً محدداً. فيما يلي فهرس شامل ومفصل لكل راوتر:
</p>

<table>
    <thead>
        <tr>
            <th style="width: 18%;">اسم الراوتر</th>
            <th style="width: 14%;">المسار (Prefix)</th>
            <th style="width: 8%;">المسارات</th>
            <th style="width: 40%;">الوظيفة والمسؤولية التشغيلية</th>
            <th style="width: 20%;">النماذج المرتبطة</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>incoming_cases.py</strong><br><small>55.8 KB</small></td>
            <td><code>/incoming-cases</code></td>
            <td>11 مساراً</td>
            <td>إدارة القضايا الواردة واستقبال الطلبات، ونظام <strong>قيد ورفع دعوى جديدة (Section 0)</strong> المخصص لاختيار الجهه (محكمة، شرطة، نيابة، تنفيذ) مع النماذج الديناميكية.</td>
            <td><code>LawIncomingCases</code>, <code>LawClients</code></td>
        </tr>
        <tr>
            <td><strong>accounting.py</strong><br><small>18.3 KB</small></td>
            <td><code>/accounting</code></td>
            <td>7 مسارات</td>
            <td>إدارة الفواتير، إنشاء عروض الأسعار، إضافة بنود الفاتورة والضرائب، إصدار باركود زاتكا (ZATCA QR Code)، وتسجيل سندات القبض.</td>
            <td><code>Invoices</code>, <code>InvoiceItems</code>, <code>ClientPayments</code></td>
        </tr>
        <tr>
            <td><strong>mobile_api.py</strong><br><small>65.4 KB</small></td>
            <td><code>/api/mobile</code></td>
            <td>44 مساراً</td>
            <td>المحرك الخلفي لتطبيق الهاتف الذكي؛ يوفر كافة نقاط الـ REST API للقضايا، الجلسات، الإشعارات، رفع المستندات بالكاميرا، والمزامنة السريعة.</td>
            <td>كافة نماذج النظام التشغيلية</td>
        </tr>
        <tr>
            <td><strong>mobile_biometrics.py</strong><br><small>8.7 KB</small></td>
            <td><code>/api/mobile/biometrics</code></td>
            <td>3 مسارات</td>
            <td>تسجيل الدخول بالبصمة الحيوية (FaceID / Fingerprint) للهواتف الذكية والتحقق من المفاتيح العامة للأجهزة.</td>
            <td><code>LawUserDevices</code>, <code>AccessProfiles</code></td>
        </tr>
        <tr>
            <td><strong>mobile_sync.py</strong><br><small>6.5 KB</small></td>
            <td><code>/api/mobile/sync</code></td>
            <td>مسار واحد</td>
            <td>مزامنة بيانات التطبيق دون اتصال (Offline-First Sync) لاسترجاع التحديثات عند عودة الاتصال بالإنترنت.</td>
            <td><code>LawCases</code>, <code>LawHearings</code>, <code>LawTasks</code></td>
        </tr>
        <tr>
            <td><strong>reports_route.py</strong><br><small>191.8 KB</small></td>
            <td>مباشر</td>
            <td>4 مسارات</td>
            <td>أضخم راوتر في النظام؛ محرك توليد ملفات الـ PDF الاحترافية عبر ReportLab (ملخصات القضايا، الكشوفات المالية، تقارير الجلسات، وطباعة الترويسات الرسمية).</td>
            <td><code>LawCases</code>, <code>Invoices</code>, <code>LawHearings</code></td>
        </tr>
        <tr>
            <td><strong>ai_assistant.py</strong><br><small>46.1 KB</small></td>
            <td><code>/api/ai</code></td>
            <td>7 مسارات</td>
            <td>المساعد القانوني الذكي؛ يتلقى أسئلة المحامين، يحللها عبر Gemini، يستعلم من قاعدة بيانات القضايا، ويصيغ الردود مع استشهادات من القوانين اليمنية.</td>
            <td><code>ai_engine</code>, <code>LawCases</code>, <code>LawHearings</code></td>
        </tr>
        <tr>
            <td><strong>documents_route.py</strong><br><small>36.8 KB</small></td>
            <td>مباشر</td>
            <td>11 مساراً</td>
            <td>إدارة ملفات ووثائق القضايا، رفع الوثائق مع الفحص الأمني، إدارة إصدارات الملفات (Versioning)، العرض المباشر (Preview)، والتحميل الآمن.</td>
            <td><code>LawDocuments</code>, <code>LawDocumentVersions</code></td>
        </tr>
        <tr>
            <td><strong>superadmin.py</strong><br><small>30.7 KB</small></td>
            <td>مباشر</td>
            <td>8 مسارات</td>
            <td>لوحة تحكم المسؤول الخارق لمنصة LawSaaS ككل؛ إدارة المكاتب المشتركة، تفعيل وتعليق الاشتراكات، وترقية باقات الاستخدام، ومتابعة إيرادات المنصة.</td>
            <td><code>LawOffices</code>, <code>AccessProfiles</code></td>
        </tr>
        <tr>
            <td><strong>intake.py</strong><br><small>24.9 KB</small></td>
            <td>مباشر</td>
            <td>9 مسارات</td>
            <td>استقطاب العملاء الجدد؛ توليد روابط النماذج العامة للمكتب، استقبال طلبات الموكلين، توقيع العقود إلكترونياً، وتحويل الطلب تلقائياً إلى موكل وقضية.</td>
            <td><code>ClientIntakeForms</code>, <code>RetainerAgreements</code></td>
        </tr>
        <tr>
            <td><strong>security_center.py</strong><br><small>22.5 KB</small></td>
            <td>مباشر</td>
            <td>15 مساراً</td>
            <td>واجهات مركز الأمان؛ لوحة متابعة الهجمات، فحص الثغرات يدوياً، مراجعة سلاسل التدقيق، وإدارة عناوين الـ IP المحظورة.</td>
            <td><code>SecurityScans</code>, <code>SecurityEvents</code></td>
        </tr>
        <tr>
            <td><strong>judgments.py</strong><br><small>20.6 KB</small></td>
            <td>مباشر</td>
            <td>7 مسارات</td>
            <td>إدارة الأحكام القضائية (ابتدائي، استئناف، عليا)، تسجيل منطوق الحكم، تواريخ الاستئناف، وحالة قابلية الحكم للتنفيذ.</td>
            <td><code>LawJudgments</code>, <code>LawCases</code></td>
        </tr>
        <tr>
            <td><strong>matters_route.py</strong><br><small>19.5 KB</small></td>
            <td>مباشر</td>
            <td>7 مسارات</td>
            <td>إدارة ملفات القضايا الرئيسية (Matters Management) من قيد، تصنيف، تحديث الحالة، وتعيين المحامين المسؤولين.</td>
            <td><code>LawCases</code>, <code>LawClients</code></td>
        </tr>
        <tr>
            <td><strong>correspondences.py</strong><br><small>19.1 KB</small></td>
            <td>مباشر</td>
            <td>8 مسارات</td>
            <td>إدارة المراسلات الصادرة والواردة الرسمية للمكتب، ربط الخطابات بالقضايا والمحاكم، وتتبع التسليم والاستلام.</td>
            <td><code>LawCorrespondences</code>, <code>LawCases</code></td>
        </tr>
        <tr>
            <td><strong>parties.py</strong><br><small>18.9 KB</small></td>
            <td>مباشر</td>
            <td>5 مسارات</td>
            <td>إدارة أطراف الدعاوى (المدعين، المدعى عليهم، المتدخلين، الشركاء) وتفاصيل صفاتهم القانونية وعناوينهم.</td>
            <td><code>LawParties</code>, <code>LawCases</code></td>
        </tr>
        <tr>
            <td><strong>trust_accounts_route.py</strong><br><small>16.5 KB</small></td>
            <td>مباشر</td>
            <td>6 مسارات</td>
            <td>إدارة حسابات أمانات الموكلين؛ متابعة المبالغ المحتجزة للتركات أو مبالغ التسويات، وضمان عزلها التام عن أموال المكتب.</td>
            <td><code>LawTrustAccounts</code>, <code>LawTrustTransactions</code></td>
        </tr>
        <tr>
            <td><strong>timeline_route.py</strong><br><small>16.4 KB</small></td>
            <td>مباشر</td>
            <td>مساران</td>
            <td>العرض الزمني التفاعلي لمراحل القضية (Timeline View)؛ يجمع الجلسات، المذكرات، الأحكام، والإجراءات في خط زمني موحد.</td>
            <td><code>LawCases</code>, <code>LawHearings</code>, <code>LawPleadings</code></td>
        </tr>
        <tr>
            <td><strong>notes.py</strong><br><small>15.9 KB</small></td>
            <td>مباشر</td>
            <td>7 مسارات</td>
            <td>الملاحظات السرية وسجلات الاجتماعات الداخلية الخاصة بفريق المحاماة حول استراتيجيات القضايا.</td>
            <td><code>LawNotes</code>, <code>LawCases</code></td>
        </tr>
        <tr>
            <td><strong>pleadings.py</strong><br><small>14.7 KB</small></td>
            <td>مباشر</td>
            <td>6 مسارات</td>
            <td>إدارة المذكرات القضائية، عرائض الدعاوى، واللوائح الجوابية ومذكرات الطعن، وتتبع مواعيد تقديمها للمحكمة.</td>
            <td><code>LawPleadings</code>, <code>LawCases</code></td>
        </tr>
        <tr>
            <td><strong>power_of_attorney.py</strong><br><small>14.0 KB</small></td>
            <td>مباشر</td>
            <td>4 مسارات</td>
            <td>إدارة الوكالات القانونية، أرقام توثيقها، تواريخ انتهائها، والتنبيه التلقائي قبل سقوط صلاحية التوكيل.</td>
            <td><code>LawPowerOfAttorney</code>, <code>LawClients</code></td>
        </tr>
        <tr>
            <td><strong>client_portal.py</strong><br><small>14.0 KB</small></td>
            <td><code>/client-portal</code></td>
            <td>8 مسارات</td>
            <td>بوابة الموكل الإلكترونية؛ تتيح للعملاء تسجيل الدخول لمتابعة مجريات قضاياهم، مواعيد الجلسات، تحميل الأحكام، وسداد الفواتير.</td>
            <td><code>LawClients</code>, <code>LawCases</code>, <code>Invoices</code></td>
        </tr>
        <tr>
            <td><strong>timesheet.py</strong><br><small>13.7 KB</small></td>
            <td>مباشر</td>
            <td>5 مسارات</td>
            <td>تسجيل ساعات عمل المحامين على القضايا والمهام لحساب الأتعاب القائمة على الأجر بالساعة (Billable Hours).</td>
            <td><code>LawTimesheets</code>, <code>LawCases</code></td>
        </tr>
        <tr>
            <td><strong>rag_router.py</strong><br><small>13.7 KB</small></td>
            <td><code>/api/rag</code></td>
            <td>7 مسارات</td>
            <td>خدمات الفهرسة والبحث الدلالي؛ رفع مستندات السوابق القضائية واسترجاع النصوص ذات الصلة عبر المتجهات (Vector Search).</td>
            <td><code>rag_engine</code>, <code>LawDocuments</code></td>
        </tr>
        <tr>
            <td><strong>executions.py</strong><br><small>12.6 KB</small></td>
            <td>مباشر</td>
            <td>4 مسارات</td>
            <td>إجراءات التنفيذ الجبري للأحكام والسندات التنفيذية أمام محاكم التنفيذ، ومتابعة الحجوزات البنكية والإفصاحات.</td>
            <td><code>LawExecutions</code>, <code>LawCases</code></td>
        </tr>
        <tr>
            <td><strong>limitations.py</strong><br><small>12.3 KB</small></td>
            <td>مباشر</td>
            <td>5 مسارات</td>
            <td>حاسبة مدد السقوط والتقادم القانوني؛ حساب مواعيد الطعن بالاستئناف والنقض والتنبيه الحرج قبل فوات الميعاد.</td>
            <td><code>LawLimitations</code>, <code>LawCases</code></td>
        </tr>
        <tr>
            <td><strong>smart_search_route.py</strong><br><small>11.9 KB</small></td>
            <td>مباشر</td>
            <td>مساران</td>
            <td>محرك البحث الذكي الشامل؛ يتيح البحث اللحظي في كافة بيانات النظام (قضايا، موكلين، خصوم، مستندات) من شريط بحث واحد.</td>
            <td>كافة نماذج النظام</td>
        </tr>
        <tr>
            <td><strong>yemeni_laws.py</strong><br><small>11.3 KB</small></td>
            <td><code>/api/laws</code></td>
            <td>6 مسارات</td>
            <td>مكتبة القوانين اليمنية؛ استعراض والبحث في نصوص المواد التشريعية وأحكام المحكمة العليا المضمنة بالنظام.</td>
            <td><code>YemeniLawDocument</code>, <code>core.yemeni_laws</code></td>
        </tr>
        <tr>
            <td><strong>team_management.py</strong><br><small>11.1 KB</small></td>
            <td>مباشر</td>
            <td>4 مسارات</td>
            <td>إدارة فريق عمل المكتب؛ إضافة المحامين والسكرتارية وتحديد أدوارهم وصلاحياتهم وتعيينهم على القضايا.</td>
            <td><code>AccessProfiles</code>, <code>LawRoles</code></td>
        </tr>
        <tr>
            <td><strong>expenses.py</strong><br><small>10.2 KB</small></td>
            <td>مباشر</td>
            <td>4 مسارات</td>
            <td>تسجيل المصروفات القضائية والنثرية على القضايا، وإرفاق سندات المصاريف لإضافتها في المطالبات المالية للموكلين.</td>
            <td><code>LawExpenses</code>, <code>LawCases</code></td>
        </tr>
        <tr>
            <td><strong>client_profile_route.py</strong><br><small>9.8 KB</small></td>
            <td>مباشر</td>
            <td>4 مسارات</td>
            <td>الملف الشامل للموكل (360 Client View)؛ يعرض كافة قضايا الموكل، مستنداته، فواتيره، ورصيده المالي في صفحة موحدة.</td>
            <td><code>LawClients</code>, <code>LawCases</code>, <code>Invoices</code></td>
        </tr>
        <tr>
            <td><strong>calendar_route.py</strong><br><small>9.7 KB</small></td>
            <td>مباشر</td>
            <td>مساران</td>
            <td>التقويم القانوني التفاعلي؛ يعرض الجلسات والمواعيد والمهام والزيارات في واجهة تقويم شهرية وأسبوعية.</td>
            <td><code>LawHearings</code>, <code>LawTasks</code></td>
        </tr>
        <tr>
            <td><strong>kanban.py</strong><br><small>9.2 KB</small></td>
            <td><code>/kanban</code></td>
            <td>6 مسارات</td>
            <td>لوحة كانبان التفاعلية لإدارة القضايا بسحب وإفلات البطاقات (جديدة، قيد التحضير، متداولة بالجلسات، صدر حكم، مغلقة).</td>
            <td><code>LawCases</code></td>
        </tr>
        <tr>
            <td><strong>legal_references.py</strong><br><small>8.0 KB</small></td>
            <td>مباشر</td>
            <td>4 مسارات</td>
            <td>أرشفة وتصنيف المراجع الفقهية والسوابق القضائية ومبادئ المحكمة العليا للرجوع إليها أثناء إعداد اللوائح.</td>
            <td><code>LawLegalReferences</code></td>
        </tr>
        <tr>
            <td><strong>api_case_recipients.py</strong><br><small>6.1 KB</small></td>
            <td>مباشر</td>
            <td>3 مسارات</td>
            <td>إدارة المستلمين والجهات المعنية بالقضايا لإرسال الإشعارات الآلية ومشاركتها عبر الواتساب أو البريد.</td>
            <td><code>LawCases</code>, <code>LawClients</code></td>
        </tr>
        <tr>
            <td><strong>login_log___sessions.py</strong><br><small>5.5 KB</small></td>
            <td>مباشر</td>
            <td>3 مسارات</td>
            <td>سجل جلسات الدخول؛ يعرض الجلسات الفعالة، عناوينات الـ IP، الأجهزة المستخدمة، ويتيح إنهاء الجلسات عن بعد.</td>
            <td><code>AuthSessions</code>, <code>AccessProfiles</code></td>
        </tr>
        <tr>
            <td><strong>advanced_operations.py</strong><br><small>5.1 KB</small></td>
            <td>مباشر</td>
            <td>مساران</td>
            <td>العمليات المتقدمة؛ الأرشفة المجمعة، تصدير قواعد البيانات، والمهام الإدارية الكبرى لمدير المكتب.</td>
            <td>كافة النماذج الرئيسية</td>
        </tr>
        <tr>
            <td><strong>reference_data.py</strong><br><small>4.8 KB</small></td>
            <td>مباشر</td>
            <td>4 مسارات</td>
            <td>إدارة البيانات المرجعية للنظام (قوائم المحاكم، درجات التقاضي، أنواع القضايا، تصنيفات المذكرات).</td>
            <td><code>LawReferenceData</code></td>
        </tr>
        <tr>
            <td><strong>conflict_check.py</strong><br><small>3.4 KB</small></td>
            <td>مباشر</td>
            <td>مساران</td>
            <td>واجهة فحص تضارب المصالح للمحامين قبل قبول أي توكيل أو قضية جديدة مع توليد تقرير فحص رسمي.</td>
            <td><code>core.conflict_checker</code></td>
        </tr>
        <tr>
            <td><strong>smart_automation_route.py</strong><br><small>23.3 KB</small></td>
            <td>مباشر</td>
            <td>11 مساراً</td>
            <td>إعداد قواعد الأتمتة الذكية والمهام التلقائية وفق محددات مشروطة (Triggers and Actions).</td>
            <td><code>LawWorkflowRules</code></td>
        </tr>
        <tr>
            <td><strong>contract_analyzer.py</strong><br><small>1.1 KB</small></td>
            <td>مباشر</td>
            <td>مسار واحد</td>
            <td>واجهة محلل العقود الذكي؛ تمكن المحامي من رفع العقد لتحليله واستخراج الثغرات والالتزامات عبر الذكاء الاصطناعي.</td>
            <td><code>rag_engine</code></td>
        </tr>
        <tr>
            <td><strong>advanced.py</strong><br><small>591 B</small></td>
            <td>-</td>
            <td>0 مسار</td>
            <td>ملف غير مستخدم (مسودة سابقة تم استبدالها بـ <code>advanced_operations.py</code>).</td>
            <td>-</td>
        </tr>
        <tr>
            <td><strong>api</strong> (بدون امتداد)<br><small>0 B</small></td>
            <td>-</td>
            <td>0 مسار</td>
            <td>ملف فارغ تماماً تم إنشاؤه بالخطأ (يجب حذفه).</td>
            <td>-</td>
        </tr>
    </tbody>
</table>
""")

# ==================== 9. CHAPTER 7: AI & RAG ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل السابع: الدليل المرجعي لمحركات الذكاء الاصطناعي والتوليد المعزز</h1>
<p class="lead-text">
ينفرد نظام LawSaaS بوجود محركين متكاملين للذكاء الاصطناعي: محرك التخاطب الذكي والاستعلام المباشر (<code>ai_engine/</code>)، ومحرك التوليد المعزز بالاسترجاع السندي والفهرسة المتجهية (<code>rag_engine/</code>).
</p>

<h2>1. محرك الذكاء الاصطناعي التفاعلي المباشر (ai_engine/)</h2>
<div class="card-grid">
    <div class="feature-card">
        <div class="feature-card-title">🤖 llm_service.py (18.5 KB)</div>
        <div class="feature-card-desc">
            بوابة الاتصال الرسمية بنماذج Google Gemini. تتولى تهيئة المفاتيح بأمان، ضبط درجات الحرارة (Temperature)، بناء برومبت المحامي العربي المتخصص، ومعالجة أخطاء الاتصال.
        </div>
    </div>
    <div class="feature-card">
        <div class="feature-card-title">🎯 intent_detector.py (30.4 KB)</div>
        <div class="feature-card-desc">
            كاشف النوايا القانونية؛ يحلل نص استفسار المستخدم ليحدد هل يريد: (استعلام عن موعد جلسة، صياغة مذكرة دعوى، البحث عن سابقة قضائية، أو حساب تقادم زمني).
        </div>
    </div>
    <div class="feature-card">
        <div class="feature-card-title">🔍 db_query_engine.py (37.7 KB)</div>
        <div class="feature-card-desc">
            محرك الاستعلام الذكي؛ يحول الأسئلة المكتوبة باللغة العربية الطبيعية إلى استعلامات SQL آمنة ومحصنة مع تطبيق العزل الصارم لمكتب المستخدم (<code>office_id</code>).
        </div>
    </div>
    <div class="feature-card">
        <div class="feature-card-title">📝 document_generator.py (14.0 KB)</div>
        <div class="feature-card-desc">
            مولد الصياغات القانونية؛ يقوم بتوليد لوائح الدعاوى، مذكرات الدفوع، والإنذارات الرسمية مع ملء بيانات أطراف الدعوى والوقائع تلقائياً من قاعدة البيانات.
        </div>
    </div>
</div>

<h2>2. قاعدة المعارف القانونية اليمنية (ai_engine/knowledge_base/)</h2>
<table>
    <thead>
        <tr>
            <th style="width: 25%;">الملف</th>
            <th style="width: 50%;">الوظيفة والمحتوى</th>
            <th style="width: 25%;">الأهمية والاستخدام</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>yemeni_laws.py</strong><br><small>37.2 KB</small></td>
            <td>نصوص ومواد القوانين اليمنية الرئيسية وفهارسها القانونية لإرشاد محرك الذكاء الاصطناعي وتزويده بالمواد الصحيحة أثناء صياغة المذكرات.</td>
            <td>""" + badge("معرفي حرج", "ai") + """</td>
        </tr>
        <tr>
            <td><strong>court_system.py</strong><br><small>35.2 KB</small></td>
            <td>هيكلية النظام القضائي اليمني؛ اختصاصات المحاكم الابتدائية، الشعب الاستئنافية، والدوائر القضائية بالمحكمة العليا وتوزيعها المكاني والنوعي.</td>
            <td>""" + badge("اختصاص قضائي", "ai") + """</td>
        </tr>
        <tr>
            <td><strong>document_templates.py</strong><br><small>24.5 KB</small></td>
            <td>هياكل وقوالب الصياغة المعتمدة للمذكرات والمرافعات والعرائض في المحاكم اليمنية لضمان مطابقتها للأعراف القضائية.</td>
            <td>""" + badge("صياغة قانونية", "ai") + """</td>
        </tr>
        <tr>
            <td><strong>legal_procedures.py</strong><br><small>11.9 KB</small></td>
            <td>دليل الإجراءات القضائية؛ مواعيد الطعن، مدد الإعلانات، وضوابط تقديم الطلبات العارضة أمام القضاء.</td>
            <td>""" + badge("إجراءات وقواعد", "ai") + """</td>
        </tr>
    </tbody>
</table>

<h2>3. محرك التوليد المعزز بالاسترجاع (rag_engine/)</h2>
<p>
يتيح هذا المحرك للمحامي رفع آلاف الصفحات من الأحكام والعقود، والبحث فيها دلالياً بالمعنى وليس بمجرد الكلمات المفتاحية:
</p>
<ul>
    <li><strong>rag_engine/core/chunker.py:</strong> تقسيم المستندات القانونية الطويلة إلى مقاطع دلالية متوازنة مع الحفاظ على سياق الفقرات القانونية.</li>
    <li><strong>rag_engine/core/embedder.py:</strong> تحويل المقاطع النصية إلى متجهات رياضية دلالية (Vector Embeddings).</li>
    <li><strong>rag_engine/core/vector_store.py:</strong> فهرسة المتجهات وتخزينها لحساب درجة التشابه واسترجاع الفقرات الأكثر صلة بطلب المحامي.</li>
    <li><strong>rag_engine/loaders/ocr_engine.py & pdf_loader.py:</strong> استخراج النصوص من ملفات الـ PDF المصورة عبر تقنيات التعرف الضوئي Tesseract و Poppler.</li>
    <li><strong>rag_engine/services/analyzer_service.py:</strong> الفحص الآلي للعقود واكتشاف البنود المجحفة ومخاطر الالتزامات والشرط الجزائي.</li>
</ul>
""")

# ==================== 10. CHAPTER 8: TEMPLATES ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل الثامن: الدليل المرجعي لواجهات المستخدم وقوالب العرض (73 قالباً)</h1>
<p class="lead-text">
تعتمد منصة LawSaaS على <strong>73 قالب Jinja2</strong> منسقاً بأعلى المعايير، يدعم اتجاه الكتابة العربي من اليمين لليسار (RTL)، ومقسماً وفق قطاعات النظام التشغيلية.
</p>

<h2>1. القوالب المركزية وقوالب لوحة التحكم (templates/)</h2>
<table>
    <thead>
        <tr>
            <th style="width: 25%;">القالب الرئيسي</th>
            <th style="width: 50%;">الوظيفة والمكونات المعروضة</th>
            <th style="width: 25%;">الراوتر المرتبط</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>templates/base.html</strong><br><small>55.6 KB</small></td>
            <td>القالب الأم (Master Layout) لكافة صفحات لوحة التحكم؛ يضم القائمة الجانبية الموحدة، الترويسة العلوية، زر المساعد الذكي، ملفات الـ CSS والـ JS، وتنبيهات النظام.</td>
            <td>مستورد في كافة قوالب لوحة التحكم</td>
        </tr>
        <tr>
            <td><strong>dashboard.html</strong><br><small>31.5 KB</small></td>
            <td>شاشة لوحة التحكم الإحصائية الرئيسية؛ تعرض مؤشرات القضايا النشطة، مواعيد الجلسات القادمة، التدفقات النقدية، والمخططات البيانية.</td>
            <td><code>main.py</code> (المسار <code>/dashboard</code>)</td>
        </tr>
        <tr>
            <td><strong>cases.html & case_details.html</strong></td>
            <td>جدول إدارة القضايا مع الفلاتر المتقدمة، وصفحة الملف التفصيلي للقضية (معلومات المحكمة، الأطراف، الجلسات، المذكرات، والأتعاب).</td>
            <td><code>matters_route.py</code></td>
        </tr>
        <tr>
            <td><strong>hearings.html</strong></td>
            <td>جدول متابعة جلسات المحاكم القادمة والسابقة، تسجيل قرارات الجلسات ومحاضرها، وتحديد مواعيد الجلسات التالية.</td>
            <td><code>main.py</code> (مسارات الجلسات)</td>
        </tr>
        <tr>
            <td><strong>documents.html</strong></td>
            <td>مدير ملفات ومستندات القضايا؛ يدعم تصنيف المستندات، المعاينة المباشرة، وسجل إصدارات الوثائق.</td>
            <td><code>documents_route.py</code></td>
        </tr>
        <tr>
            <td><strong>ai_assistant.html</strong></td>
            <td>واجهة المحادثة التفاعلية مع المساعد القانوني الذكي؛ تدعم المراسلة الصوتية والنصية، وتوليد مذكرات الدعوى وتنزيلها.</td>
            <td><code>ai_assistant.py</code></td>
        </tr>
        <tr>
            <td><strong>automation.html</strong></td>
            <td>لوحة بناء وبرمجة قواعد سير العمل والأتمتة الذكية بدون كتابة كود (No-Code Rule Builder).</td>
            <td><code>smart_automation_route.py</code></td>
        </tr>
        <tr>
            <td><strong>security_center.html</strong></td>
            <td>لوحة مركز الأمان السيبراني؛ الرسوم البيانية للهجمات، نقاط الضعف، مراقبة الجلسات، وسجلات فحص الفيروسات.</td>
            <td><code>security_center.py</code></td>
        </tr>
        <tr>
            <td><strong>superadmin.html</strong></td>
            <td>شاشة المسؤول الخارق لإدارة مكاتب المحاماة المشتركة في المنصة، تفعيل الحسابات، ومراقبة موارد الخادم.</td>
            <td><code>superadmin.py</code></td>
        </tr>
    </tbody>
</table>

<h2>2. القوالب الفرعية التخصصية (Sub-Directories)</h2>
<table>
    <thead>
        <tr>
            <th style="width: 25%;">المجلد الفرعي</th>
            <th style="width: 25%;">القوالب الموجودة</th>
            <th style="width: 50%;">الوظيفة والدور في المنصة</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>templates/incoming_cases/</strong></td>
            <td><code>hub.html</code><br><code>section_view.html</code></td>
            <td>بوابة القضايا الواردة المحدثة؛ تضم شاشة الاختيار الرئيسية (Hub) ونموذج <strong>قيد ورفع دعوى جديدة (Section 0)</strong> الذي يتبدل ديناميكياً باختيار الجهه المستهدفة.</td>
        </tr>
        <tr>
            <td><strong>templates/accounting/</strong></td>
            <td><code>invoices.html</code><br><code>invoice_form.html</code><br><code>invoice_pdf.html</code></td>
            <td>منظومة الفوترة والمحاسبة؛ جدول الفواتير، نموذج إنشاء وتعديل الفاتورة مع حساب الضرائب، وقالب الطباعة الرسمي مع باركود زاتكا.</td>
        </tr>
        <tr>
            <td><strong>templates/client_portal/</strong></td>
            <td><code>base.html</code>, <code>dashboard.html</code>, <code>cases.html</code>, <code>contracts.html</code>, <code>hearings.html</code>, <code>finance.html</code>, <code>documents.html</code></td>
            <td>البوابة المستقلة للموكلين؛ واجهة خاصة منفصلة تتيح للموكل الاطلاع على قضاياه، توقيع العقود إلكترونياً، والاطلاع على فواتيره ومواعيد جلساته.</td>
        </tr>
        <tr>
            <td><strong>templates/intake/</strong></td>
            <td><code>public_form.html</code><br><code>intake_list.html</code><br><code>e_sign.html</code><br><code>signed_contract_pdf.html</code></td>
            <td>نماذج استقطاب الموكلين التفاعلية عبر الإنترنت، صفحة التوقيع الإلكتروني على الشاشة باللمس، وتوليد العقد النهائي الموقع بصيغة PDF.</td>
        </tr>
        <tr>
            <td><strong>templates/kanban/</strong></td>
            <td><code>board.html</code></td>
            <td>لوحة كانبان التفاعلية لفرز وتحريك القضايا والمهام بين مراحل الإنجاز بالسحب والإفلات (Drag and Drop).</td>
        </tr>
        <tr>
            <td><strong>templates/components/</strong></td>
            <td><code>report_letterhead.html</code></td>
            <td>الترويسة الرسمية الموحدة للمكتب، تضم الشعار والاسم والبيانات الرسمية وتُطبع على كافة التقارير والمذكرات الصادرة.</td>
        </tr>
    </tbody>
</table>
""")

# ==================== 11. CHAPTER 9: MAINTENANCE & MEDIA ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل التاسع: الدليل المرجعي لأدوات الصيانة، السكربتات والأصول المضمنة</h1>
<p class="lead-text">
يحتوي المستودع على أدوات مساعدة لصيانة الخادم وقاعدة البيانات، بالإضافة إلى حزم مضمنة وأصول إنتاج إعلامية. يوضح هذا الفصل حقيقة ودور كل منها:
</p>

<h2>1. سكربتات الصيانة وأدوات سطر الأوامر (CLI Tools)</h2>
<table>
    <thead>
        <tr>
            <th style="width: 25%;">اسم السكربت</th>
            <th style="width: 50%;">الوظيفة المحددة</th>
            <th style="width: 25%;">حالة الاستخدام والتوصية</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>create_superadmin.py</strong><br><small>4,470 بايت</small></td>
            <td>سكربت طرفي (CLI) تفاعلي؛ ينشئ حساب المسؤول الخارق (Superadmin) في قاعدة البيانات مع تشفير كلمة المرور بـ <code>bcrypt</code>، ومنحه مكتب النظام الرئيسي.</td>
            <td>""" + badge("أداة تشغيل أساسية", "core") + """<br>يُستخدم عند تجهيز الخادم لأول مرة.</td>
        </tr>
        <tr>
            <td><strong>check_admin_user.py & check_db.py</strong></td>
            <td>فحص الاتصال بقاعدة البيانات والتحقق من وجود الحساب الإداري وصحة هيكل الجداول.</td>
            <td>""" + badge("أداة فحص واختبار", "active") + """</td>
        </tr>
        <tr>
            <td><strong>export_all_databases.py</strong><br><small>7,770 بايت</small></td>
            <td>تصدير كافة جداول وبيانات النظام إلى ملفات SQL و CSV كنسخة احتياطية آمنة لحالات الطوارئ.</td>
            <td>""" + badge("أداة نسخ احتياطي", "active") + """</td>
        </tr>
        <tr>
            <td><strong>test_login.py</strong><br><small>1,076 بايت</small></td>
            <td>اختبار برمجي آلي لعملية تسجيل الدخول، التحقق من كلمات المرور، وإصدار ملفات تعريف الارتباط للجلسات.</td>
            <td>""" + badge("اختبار جودة", "active") + """</td>
        </tr>
        <tr>
            <td><strong>deploy.bat</strong><br><small>323 بايت</small></td>
            <td>ملف أوامر دفعي لنظام Windows؛ يقوم بسحب آخر التحديثات وبناء وتشغيل الحاويات عبر <code>docker-compose</code>.</td>
            <td>""" + badge("نشر محلي", "cfg") + """</td>
        </tr>
    </tbody>
</table>

<h2>2. الحزم المضمنة والأصول الإعلامية (Vendored & Media Assets)</h2>
<div class="callout callout-info">
    <div class="callout-title">📦 حزمة Poppler المضمنة (poppler/ - 480 ملفاً)</div>
    <p>
        مجلد <code>poppler/</code> يمثل توزيعة ثنائية كاملة (C++ Binaries & Libraries) لأداة Poppler الشهيرة. وُضعت داخل المستودع لتمكين بيئة التطوير المحلية على نظام Windows من قراءة ملفات الـ PDF المصورة واستخراج النصوص منها بواسطة Tesseract OCR دون الحاجة لتنصيب برامج خارجية على جهاز المطور.
    </p>
</div>

<div class="callout callout-success">
    <div class="callout-title">🎬 أصول الإنتاج المرئي والهوية (LawSaaS_Media_Production/ - 110 ملفات)</div>
    <p>
        يحتوي هذا المجلد على الأصول الإعلامية الكاملة لمنصة <strong>وزيرك - LawSaaS</strong>، وتشمل:
    </p>
    <ul>
        <li><strong>01_Brand_Identity:</strong> شعارات المنصة المعتمدة (الميزان الذهبي، شعار وزيرك) ودليل الهوية البصرية.</li>
        <li><strong>02_Main_Promo:</strong> الفيديوهات الترويجية الرئيسية للمنصة بالأبعاد المختلفة (16:9 شاشات العرض، 9:16 تيك توك وريلز، 1:1 إنستغرام).</li>
        <li><strong>07_Scripts_And_Voiceovers:</strong> النصوص الإعلانية والتسجيلات الصوتية الاحترافية للتعليق الصوتي.</li>
        <li><strong>08_Project_Source_Files:</strong> ملفات مشاريع التصميم والمشاهد والواجهات الملتقطة أثناء إعداد الحملات الترويجية.</li>
    </ul>
</div>
""")

# ==================== 12. CHAPTER 10: OPERATIONAL WORKFLOWS ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل العاشر: مخططات مسارات العمل وسير العمليات الحيوية</h1>
<p class="lead-text">
لفهم كيفية تعاون الملفات في بيئة التشغيل الفعلية، يوضح هذا الفصل مسارات البيانات من لحظة نقر المستخدم في المتصفح، مروراً بالوسيطات والراوترات، وحتى استقرارها في قاعدة البيانات.
</p>

<h2>المسار الأول: دورة قيد ورفع دعوى جديدة (Lawsuit Intake Workflow)</h2>
<div class="workflow-container">
    <div class="workflow-step">
        <div class="step-num">1</div>
        <div class="step-content">
            <div class="step-title">المستخدم يفتح شاشة رفع دعوى جديدة ويختار الجهه المستهدفة</div>
            <div class="step-desc">يقوم المحامي بفتح القضايا الواردة، واختيار بطاقة "قيد ورفع دعوى جديدة". بمجرد اختيار الجهه (محكمة، شرطة، نيابة، تنفيذ)، تتغير حقول النموذج فوراً بواسطة JavaScript بدون إعادة تحميل الصفحة.</div>
            <div class="step-files">الملفات: templates/incoming_cases/hub.html ➔ section_view.html</div>
        </div>
    </div>
    <div class="arrow-down">▼</div>
    <div class="workflow-step">
        <div class="step-num">2</div>
        <div class="step-content">
            <div class="step-title">إرسال طلب POST مشفر مع التحقق من الجلسة والصلاحيات</div>
            <div class="step-desc">يُرسل المتصفح البيانات إلى نقطة النهاية <code>/incoming-cases/section/0</code>. تستلم الوسيطة الطلب، وتتحقق <code>dependencies.py</code> من جلسة المحامي وصلاحيته وحقن <code>user.office_id</code>.</div>
            <div class="step-files">الملفات: main.py ➔ dependencies.py ➔ routers/incoming_cases.py</div>
        </div>
    </div>
    <div class="arrow-down">▼</div>
    <div class="workflow-step">
        <div class="step-num">3</div>
        <div class="step-content">
            <div class="step-title">التحقق من البيانات وإنشاء سجل الدعوى في قاعدة البيانات</div>
            <div class="step-desc">يقوم الراوتر ببناء كائن <code>LawIncomingCases</code>، وتعيين الحقول التخصصية (اسم الخصم، هوية الخصم، رقم الوكالة، قيمة المطالبة، والأسانيد)، وحفظ السجل مع عزل المكتب الصارم.</div>
            <div class="step-files">الملفات: routers/incoming_cases.py ➔ database/models.py ➔ database/database.py</div>
        </div>
    </div>
    <div class="arrow-down">▼</div>
    <div class="workflow-step">
        <div class="step-num">4</div>
        <div class="step-content">
            <div class="step-title">تسجيل العملية في سجل التدقيق وإعادة التوجيه مع رسالة النجاح</div>
            <div class="step-desc">يستدعي الراوتر دالة <code>log_audit_action</code> لتوثيق العملية، ثم يعيد توجيه المحامي إلى جدول الدعاوى مع إشعار نجاح العملية.</div>
            <div class="step-files">الملفات: core/audit.py ➔ LawAuditLog ➔ templates/incoming_cases/section_view.html</div>
        </div>
    </div>
</div>

<h2>المسار الثاني: دورة تسجيل الدخول وحماية الجلسات (Authentication Lifecycle)</h2>
<div class="workflow-container">
    <div class="workflow-step">
        <div class="step-num">1</div>
        <div class="step-content">
            <div class="step-title">المحامي يدخل البريد الإلكتروني وكلمة المرور</div>
            <div class="step-desc">يقدم المستخدم بيانات اعتماده عبر صفحة الدخول، ويتم إرسال الطلب عبر قناة HTTPS مشفرة.</div>
            <div class="step-files">الملفات: templates/login.html ➔ main.py (POST /login)</div>
        </div>
    </div>
    <div class="arrow-down">▼</div>
    <div class="workflow-step">
        <div class="step-num">2</div>
        <div class="step-content">
            <div class="step-title">فحص معدل الطلبات ومنع التخمين (Rate Limiting Check)</div>
            <div class="step-desc">تفحص وحدة <code>rate_limiter.py</code> عنوان الـ IP؛ إذا تجاوز المحاولات المسموحة يتم قفل الحساب مؤقتاً وتسجيل إنذار في مركز الأمان.</div>
            <div class="step-files">الملفات: core/rate_limiter.py ➔ core/security_center/monitor_middleware.py</div>
        </div>
    </div>
    <div class="arrow-down">▼</div>
    <div class="workflow-step">
        <div class="step-num">3</div>
        <div class="step-content">
            <div class="step-title">مطابقة التجزئة المشفرة لكلمة المرور والتحقق من حالة الحساب</div>
            <div class="step-desc">تستعلم <code>main.py</code> عن المستخدم في <code>AccessProfiles</code>، وتتحقق من كلمة المرور عبر <code>verify_password</code> (bcrypt). في حال تطابقها يُفحص هل فُعّل التحقق الثنائي (2FA).</div>
            <div class="step-files">الملفات: database/models.py ➔ core/security.py</div>
        </div>
    </div>
    <div class="arrow-down">▼</div>
    <div class="workflow-step">
        <div class="step-num">4</div>
        <div class="step-content">
            <div class="step-title">توليد رمز الجلسة العشوائي وتجزئته في قاعدة البيانات وإصدار الكوكيز</div>
            <div class="step-desc">يُنشأ رمز جلسة سري <code>raw_token</code>، ويُخزن تجزئته (Hash) في جدول <code>AuthSessions</code>، بينما يُرسل الرمز الخام كـ Cookie مشفر بخاصية <code>HttpOnly, Secure, SameSite=Lax</code>.</div>
            <div class="step-files">الملفات: core/security.py ➔ AuthSessions ➔ dependencies.py</div>
        </div>
    </div>
</div>

<h2>المسار الثالث: رفع وفحص وتخزين المستندات بأمان (Secure Document Storage)</h2>
<div class="workflow-container">
    <div class="workflow-step">
        <div class="step-num">1</div>
        <div class="step-content">
            <div class="step-title">المستخدم يرفع وثيقة أو حكماً قضائياً</div>
            <div class="step-desc">يتم اختيار الملف عبر واجهة المستندات، ويُرسل كـ Multipart Form Data إلى راوتر المستندات.</div>
            <div class="step-files">الملفات: templates/documents.html ➔ routers/documents_route.py</div>
        </div>
    </div>
    <div class="arrow-down">▼</div>
    <div class="workflow-step">
        <div class="step-num">2</div>
        <div class="step-content">
            <div class="step-title">الفحص الأمني الصارم (Magic Bytes & ClamAV Scan)</div>
            <div class="step-desc">تفحص <code>upload_security.py</code> التوقيع السحري للملف للتأكد من أنه PDF أو صورة حقيقية وليس ملفاً تنفيذياً ملغماً، وتمرره لـ <code>file_scanner.py</code> لكشف الفيروسات.</div>
            <div class="step-files">الملفات: core/upload_security.py ➔ core/security_center/file_scanner.py</div>
        </div>
    </div>
    <div class="arrow-down">▼</div>
    <div class="workflow-step">
        <div class="step-num">3</div>
        <div class="step-content">
            <div class="step-title">توليد اسم عشوائي آمن والتخزين في مسار المكتب المعزول</div>
            <div class="step-desc">يُعاد تسمية الملف برمز UUID سداسي فريد لمنع استبدال الملفات وتخطي المسارات، ويُخزن داخل المجلد المعزول <code>uploads/offices/{office_id}/</code>.</div>
            <div class="step-files">الملفات: routers/documents_route.py ➔ OS Storage System</div>
        </div>
    </div>
    <div class="arrow-down">▼</div>
    <div class="workflow-step">
        <div class="step-num">4</div>
        <div class="step-content">
            <div class="step-title">تسجيل البيانات الوصفية والإصدار في قاعدة البيانات ومحرك RAG</div>
            <div class="step-desc">يُسجل المسار في جدول <code>LawDocuments</code>، ويُضاف إصدار في <code>LawDocumentVersions</code>، ثم يُرسل إلى <code>rag_engine</code> لاستخراج النصوص وفهرستها للبحث الدلالي.</div>
            <div class="step-files">الملفات: database/models.py ➔ rag_engine/loaders/pdf_loader.py ➔ vector_store.py</div>
        </div>
    </div>
</div>
""")

# ==================== 13. CHAPTER 11: SENSITIVE FILES ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل الحادي عشر: دليل الملفات الحساسة ومحاذير التعديل</h1>
<p class="lead-text">
هناك ملفات يمثل التعديل العشوائي عليها خطورة بالغة على سلامة بيانات المنصة وعملائها. فيما يلي مصفوفة الحذر والملفات المحمية:
</p>

<table>
    <thead>
        <tr>
            <th style="width: 25%;">الملف الحرج</th>
            <th style="width: 25%;">مجال التأثير والخطر</th>
            <th style="width: 25%;">ما الذي يحدث عند التعديل الخاطئ؟</th>
            <th style="width: 25%;">بروتوكول التعديل الآمن</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>main.py</strong></td>
            <td>إطلاق الخادم، الوسيطات، وتوجيه المسارات العامة.</td>
            <td>توقف الخادم بالكامل عن العمل (Crash)، وظهور أخطاء 502 Bad Gateway لجميع المستخدمين.</td>
            <td>التحقق دائماً عبر <code>python -m py_compile main.py</code> قبل إعادة تشغيل الحاوية.</td>
        </tr>
        <tr>
            <td><strong>database/models.py</strong></td>
            <td>هيكلية الجداول والعلاقات والمفاتيح الأجنبية.</td>
            <td>فشل استعلامات الـ ORM وظهور أخطاء <code>UndefinedColumn</code> أو <code>ForeignKeyViolation</code>.</td>
            <td>توليد وتطبيق ملف ترقية عبر Alembic دائماً عند إضافة أي حقل أو جدول جديد.</td>
        </tr>
        <tr>
            <td><strong>dependencies.py</strong></td>
            <td>جلسات المستخدمين، الصلاحيات، وعزل المكاتب.</td>
            <td>تسريب بيانات المكاتب، أو حظر كافة المحامين ومنعهم من الدخول للمنصة.</td>
            <td>عدم تغيير منطق <code>get_current_user</code> أو <code>check_user_permission</code> إلا بعد اختبار دقيق.</td>
        </tr>
        <tr>
            <td><strong>core/security.py</strong></td>
            <td>تشفير كلمات المرور والرموز السرية.</td>
            <td>عجز كافة المستخدمين الحاليين عن فك تشفير كلمات مرورهم أو تسجيل الدخول.</td>
            <td>عدم تغيير خوارزمية التجزئة أو أطوال مفاتيح التشفير القديمة.</td>
        </tr>
        <tr>
            <td><strong>database/database.py</strong></td>
            <td>مجمع الاتصالات والترقية التلقائية.</td>
            <td>انهيار الاتصال بقاعدة البيانات وفقدان مزامنة الأعمدة التلقائية.</td>
            <td>الحفاظ على معالجات SQLite و PostgreSQL وعدم تعديل مهلات الاتصال دون داعٍ.</td>
        </tr>
        <tr>
            <td><strong>.env (في بيئة الإنتاج)</strong></td>
            <td>المفاتيح السرية الحية، وقواعد البيانات.</td>
            <td>توقف الخدمات السحابية، كشف المفاتيح، أو اتصال التطبيق بقاعدة بيانات خاطئة.</td>
            <td>حماية الملف بتصاريح <code>chmod 600</code> وعدم تضمينه نهائياً داخل مستودع Git.</td>
        </tr>
    </tbody>
</table>

<div class="callout callout-danger">
    <div class="callout-title">⛔ قواعد ذهبية للمطور (Safety Rules)</div>
    <ol>
        <li><strong>لا تحذف حقل <code>office_id</code> أبداً:</strong> كل استعلام وكل جدول تشغيلي يجب أن يرتبط بالمكتب لعزل بيانات المكاتب عن بعضها.</li>
        <li><strong>اعتمد الحذف الآمن (Soft Delete):</strong> عند حذف أي قضية أو موكل أو فاتورة، استخدم دائماً <code>is_deleted = 1</code> بدلاً من استدعاء <code>db.delete()</code> لضمان عدم ضياع السجلات القانونية.</li>
        <li><strong>افحص التوافقية قبل النشر:</strong> تأكد دائماً من مطابقة التعديلات لقاعدة بيانات الإنتاج السحابية (PostgreSQL).</li>
    </ol>
</div>
""")

# ==================== 14. CHAPTER 12: HYGIENE & CLEANUP ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الفصل الثاني عشر: تدقيق النظافة البرمجية (الملفات المكررة والمهملة)</h1>
<p class="lead-text">
أظهر الفحص الحي لمستودع LawSaaS وجود بعض الملفات المكررة أو القديمة التي نشأت أثناء مراحل التطوير والترقية السابقة. يوثق هذا الفصل وضع كل منها بدقة لمنع الالتباس لدى المطور:
</p>

<table>
    <thead>
        <tr>
            <th style="width: 25%;">الملف</th>
            <th style="width: 25%;">الملف البديل النشط</th>
            <th style="width: 25%;">الحالة الفنية</th>
            <th style="width: 25%;">التوصية الفنية</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>base.html</strong> (في الجذر)<br><small>42.8 KB</small></td>
            <td><strong>templates/base.html</strong><br><small>55.6 KB</small></td>
            <td>نسخة قديمة متخلفة عن القالب النشط الموجود داخل مجلد <code>templates/</code>.</td>
            <td>يمكن حذفه بأمان؛ لأن محرك Jinja2 يقرأ من مجلد <code>templates/</code> حصراً.</td>
        </tr>
        <tr>
            <td><strong>database.py</strong> (في الجذر)<br><small>28.1 KB</small></td>
            <td><strong>database/database.py</strong><br><small>28.4 KB</small></td>
            <td>نسخة أصلية قديمة قبل تنظيم طبقة قواعد البيانات في حزمة فرعية مستقلة.</td>
            <td>غير مستورد في الراوترات الحديثة؛ يُفضل أرشفته لمنع تشتت المطورين.</td>
        </tr>
        <tr>
            <td><strong>superadmin.py</strong> (في الجذر)<br><small>22.0 KB</small></td>
            <td><strong>routers/superadmin.py</strong><br><small>30.7 KB</small></td>
            <td>نسخة سابقة من راوتر المسؤول الخارق؛ استبدلت بالكامل بالراوتر المطور داخل <code>routers/</code>.</td>
            <td>يمكن حذفه بأمان لكون <code>main.py</code> يستورد راوتر <code>routers/superadmin.py</code>.</td>
        </tr>
        <tr>
            <td><strong>error_handler.py</strong> (في الجذر)<br><small>14.0 KB</small></td>
            <td><strong>core/error_handler.py</strong><br><small>14.0 KB</small></td>
            <td>ملف مكرر ومتطابق تماماً في الحجم والكود مع ملف النواة.</td>
            <td>يمكن توحيد استيراده من <code>core/error_handler.py</code> وحذف نسخة الجذر.</td>
        </tr>
        <tr>
            <td><strong>routers/advanced.py</strong><br><small>591 بايت</small></td>
            <td><strong>routers/advanced_operations.py</strong><br><small>5.1 KB</small></td>
            <td>مسودة أولية لم تكتمل، وتم تنفيذ كامل وظائفها في <code>advanced_operations.py</code>.</td>
            <td>ملف فارغ المسارات تقنياً ويمكن حذفه بأمان.</td>
        </tr>
        <tr>
            <td><strong>routers/api</strong><br><small>0 بايت</small></td>
            <td><strong>routers/mobile_api.py</strong></td>
            <td>ملف فارغ تماماً بدون امتداد أُنشئ عرضاً.</td>
            <td>يجب حذفه فوراً لتنظيف مجلد الراوترات.</td>
        </tr>
        <tr>
            <td><strong>سكربتات الترقيع (fix_*.py, patch_*.py)</strong></td>
            <td>ملفات الترحيل الرسمية <code>alembic/</code></td>
            <td>سكربتات إصلاح ومعايرة لمرة واحدة تم استخدامها أثناء ترقيات تاريخية سابقة.</td>
            <td>يُفضل نقلها لمجلد جانبي (مثل <code>tools/legacy_patches/</code>) لإبقاء الجذر نظيفاً.</td>
        </tr>
    </tbody>
</table>
""")

# ==================== 15. TECHNICAL GLOSSARY ====================
html_parts.append("""
<div class="page-break"></div>
<h1>الملحق المرجعي: قاموس المصطلحات البرمجية والمعمارية</h1>
<p class="lead-text">
دليل مصطلحات سريع يوضح المفاهيم التقنية المعتمدة في بنية LawSaaS لتعزيز الفهم البرمجي المتخصص:
</p>

<table>
    <thead>
        <tr>
            <th style="width: 25%;">المصطلح (English)</th>
            <th style="width: 25%;">المعنى بالعربية</th>
            <th style="width: 50%;">الشرح العملي داخل مشروع LawSaaS</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>Multi-Tenancy</strong></td>
            <td>تعدد المكاتب المستأجرة</td>
            <td>معمارية برمجية تسمح لعدة مكاتب محاماة باستخدام نفس النظام مع عزل بيانات كل مكتب تماماً عن الآخرين.</td>
        </tr>
        <tr>
            <td><strong>Row-Level Isolation</strong></td>
            <td>العزل على مستوى الصف</td>
            <td>آلية حماية تعتمد على إرفاق <code>office_id</code> في كل صف بقاعدة البيانات لتقييد الاستعلامات على بيانات المكتب الحالي فقط.</td>
        </tr>
        <tr>
            <td><strong>Dependency Injection</strong></td>
            <td>حقن التبعيات</td>
            <td>نمط تصميم في FastAPI (مثل <code>Depends(get_current_user)</code>) لتزويد الدوال بالمستخدم والجلسة وقاعدة البيانات تلقائياً.</td>
        </tr>
        <tr>
            <td><strong>ORM (Object Relational Mapping)</strong></td>
            <td>الربط العلائقي للكائنات</td>
            <td>تقنية برمجية (SQLAlchemy) تتيح التعامل مع جداول وسجلات قاعدة البيانات ككائنات وكلاسات Pythonية بدلاً من كتابة أوامر SQL خام.</td>
        </tr>
        <tr>
            <td><strong>Soft Delete</strong></td>
            <td>الحذف الآمن / المنطقي</td>
            <td>إخفاء السجل من العرض بتعيين <code>is_deleted = 1</code> بدلاً من حذفه الفعلي، للحفاظ على السجلات المالية والقضائية التاريخية.</td>
        </tr>
        <tr>
            <td><strong>RAG (Retrieval-Augmented Gen)</strong></td>
            <td>التوليد المعزز بالاسترجاع</td>
            <td>دمج الذكاء الاصطناعي (Gemini) مع قاعدة بيانات الوثائق القانونية لتقديم استشارات دقيقة مستندة لأحكام وسوابق حقيقية.</td>
        </tr>
        <tr>
            <td><strong>Vector Embeddings</strong></td>
            <td>التضمين المتجهي للنصوص</td>
            <td>تحويل الفقرات القانونية إلى أرقام هندسية متجهة تتيح للبحث الذكي فهم معنى النص وليس مجرد حروفه.</td>
        </tr>
        <tr>
            <td><strong>ZATCA Phase 1 QR</strong></td>
            <td>باركود هيئة الزكاة والضريبة</td>
            <td>تشفير بيانات الفاتورة (اسم المورد، الرقم الضريبي، التاريخ، القيمة، والضريبة) في كود مشفر بتنسيق TLV متوافق مع متطلبات الفوترة.</td>
        </tr>
        <tr>
            <td><strong>Session Middleware</strong></td>
            <td>وسيطة إدارة الجلسات</td>
            <td>طبقة برمجية تعترض كل طلب للموقع للتأكد من صحة كوكيز الجلسة وسلامة التشفير قبل توجيه المستخدم لصفحته.</td>
        </tr>
        <tr>
            <td><strong>Brute-Force Protection</strong></td>
            <td>حماية ضد التخمين</td>
            <td>تقييد عدد محاولات إدخال كلمة المرور الخاطئة لمنع القراصنة من تخمين الحسابات عبر برامج آلية.</td>
        </tr>
    </tbody>
</table>

<div style="margin-top: 40px; text-align: center; border-top: 2px solid #e2e8f0; padding-top: 20px; color: #64748b; font-size: 9pt;">
    نهاية الدليل المرجعي الفني — تم بحمد الله وتوفيقه توثيق مشروع LawSaaS بدقة هندسية شاملة.
</div>
</body>
</html>
""")

html_content = "\n".join(html_parts)

html_filename = "lawsaas_technical_blueprint.html"
with open(html_filename, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"HTML Book generated: {html_filename} ({len(html_content)} bytes)")

# Compile to PDF using Microsoft Edge Headless
pdf_filename = "الخريطة_التقنية_الشاملة_لمشروع_LawSaaS.pdf"
edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

if os.path.exists(edge_exe):
    print("Compiling HTML to PDF via Microsoft Edge Headless...")
    abs_html = os.path.abspath(html_filename)
    abs_pdf = os.path.abspath(pdf_filename)
    
    cmd = [
        edge_exe,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={abs_pdf}",
        abs_html
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(abs_pdf) and os.path.getsize(abs_pdf) > 1000:
        print(f"SUCCESS! PDF created: {pdf_filename} ({os.path.getsize(abs_pdf)} bytes)")
    else:
        # Try fallback without =new
        cmd[1] = "--headless"
        res = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(abs_pdf):
            print(f"SUCCESS (fallback)! PDF created: {pdf_filename} ({os.path.getsize(abs_pdf)} bytes)")
        else:
            print(f"Failed to generate PDF. Edge stderr: {res.stderr}")
else:
    print(f"Edge executable not found at {edge_exe}")

print("Book generation finished.")
