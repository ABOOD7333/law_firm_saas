"""
Security Helpers — LawSaaS
أدوات مساعدة للتحقق من أمان المدخلات والملفات المرفوعة.
"""

def validate_file_signature(content: bytes, extension: str) -> bool:
    """
    التحقق من صحة الملف بناءً على التوقيع الرقمي (Magic Bytes) وليس فقط الامتداد لمنع رفع ملفات خبيثة بامتدادات مزيفة.
    """
    if not content:
        return False
        
    ext = extension.lower().strip().replace(".", "")
    
    # التوقيعات الرقمية الشائعة (Magic Bytes)
    if ext == 'pdf':
        return content.startswith(b'%PDF')
    elif ext in ['jpg', 'jpeg']:
        return content.startswith(b'\xff\xd8\xff')
    elif ext == 'png':
        return content.startswith(b'\x89PNG\r\n\x1a\n')
    elif ext == 'gif':
        return content.startswith(b'GIF87a') or content.startswith(b'GIF89a')
    elif ext in ['docx', 'doc']:
        # تنسيق DOCX هو عبارة عن ملف ZIP مضغوط (يبدأ بـ PK\x03\x04)
        # تنسيق DOC القديم يبدأ بـ \xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1
        return content.startswith(b'PK\x03\x04') or content.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')
    elif ext == 'txt':
        # التحقق من أن الملف النصي لا يحتوي على أحرف ثنائية ملغية (Null Bytes) وهي سمة الملفات التنفيذية
        try:
            if b'\x00' in content:
                return False
            content.decode('utf-8')
            return True
        except UnicodeDecodeError:
            return False
            
    return False
