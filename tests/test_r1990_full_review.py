import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
from httpx import AsyncClient, ASGITransport
from main import app

async def run_full_suite():
    transport = ASGITransport(app=app)
    results = {}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login with R1990
        login_resp = await client.post(
            "/",
            data={"email": "R1990", "password": "admin123456"},
            follow_redirects=False
        )
        assert login_resp.status_code == 303, f"Login failed with status {login_resp.status_code}"
        cookies = dict(login_resp.cookies)
        
        # Helper to get page with auth cookies and check for expected patterns/keywords/fields
        async def check_route(route_name, path, expected_patterns=None):
            resp = await client.get(path, cookies=cookies)
            status = resp.status_code
            html = resp.text
            
            missing_elements = []
            found_elements = []
            if expected_patterns:
                for pattern, desc in expected_patterns:
                    if not re.search(pattern, html, re.IGNORECASE):
                        missing_elements.append(f"{desc} (pattern: '{pattern}')")
                    else:
                        found_elements.append(f"{desc}")
            
            has_error = (
                "Internal Server Error" in html or 
                "Traceback (most recent call last)" in html or
                status != 200
            )

            results[route_name] = {
                "path": path,
                "status": status,
                "missing": missing_elements,
                "found": found_elements,
                "has_500_or_error": has_error
            }
            return resp

        print("=== Starting Interface Audits ===")

        # 1. Dashboard
        await check_route("لوحة التحكم (Dashboard)", "/dashboard", [
            (r"لوحة التحكم|مرحباً|إحصائيات", "عنوان لوحة التحكم"),
            (r"class=[\"'].*?(card|kpi|stat|badge).*?[\"']", "بطاقات المؤشرات والإحصاءات"),
            (r"قضايا|جلسات|مهام", "أقسام متابعة العمل اليومي")
        ])

        # 2. Cases
        await check_route("إدارة القضايا (Cases)", "/cases", [
            (r"modal|إضافة قضية|قضية جديدة", "نافذة إضافة قضية جديدة"),
            (r"case_number|رقم القضية", "حقل رقم القضية"),
            (r"title|موضوع الدعوى|عنوان القضية", "حقل عنوان القضية"),
            (r"client_id|الموكل", "حقل اختيار الموكل"),
            (r"court_name|court_id|المحكمة", "حقل المحكمة المختصة")
        ])

        # 3. Hearings
        await check_route("محاضر الجلسات (Hearings)", "/hearings", [
            (r"hearing_date|تاريخ الجلسة", "حقل تاريخ الجلسة"),
            (r"decision|court_decision|قرار الجلسة|القرار", "حقل قرار الجلسة"),
            (r"requirements|طلبات الجلسة|الملاحظات|ملاحظات", "حقل طلبات وملاحظات الجلسة"),
            (r"attendees|حضور|صفة الحضور|حضر", "بيانات الحضور وأطراف الجلسة")
        ])

        # 4. Documents & DMS
        await check_route("المستندات والأرشفة (Documents)", "/documents", [
            (r"type=[\"']file[\"']|رفع مستند|إضافة وثيقة", "حقل رفع الملف والمستند"),
            (r"title|document_title|اسم المستند|عنوان الوثيقة", "حقل عنوان المستند"),
            (r"category|doc_type|تصنيف|أرشيف", "حقل التصنيف والأرشفة")
        ])

        # 5. Parties & Litigants
        await check_route("الأطراف والخصوم (Parties)", "/parties", [
            (r"party|الخصم|الطرف|أطراف", "واجهة الأطراف والخصوم"),
            (r"name|party_name|اسم الخصم|اسم الطرف", "حقل اسم الطرف"),
            (r"case_id|القضية", "ربط الطرف بالقضية"),
            (r"party_type|role|صفة الطرف|الصفة", "صفة الطرف ونوعه")
        ])

        # 6. Clients
        await check_route("سجل الموكلين (Clients)", "/clients", [
            (r"إضافة موكل|موكل جديد|clientModal", "نافذة إضافة موكل"),
            (r"name|اسم الموكل|الاسم", "حقل اسم الموكل"),
            (r"phone|رقم الهاتف|الجوال", "حقل هاتف الموكل"),
            (r"client_type|نوع الموكل|فرد|شركة", "حقل نوع الموكل (فرد / شركة)")
        ])

        # 7. Smart Global Search
        await check_route("البحث المتقدم (Search)", "/search", [
            (r"search|بحث|البحث الذكي|كلمة البحث", "شريط البحث الموحد"),
            (r"type=[\"']text[\"']|name=[\"']q[\"']", "حقل إدخال كلمة البحث"),
            (r"تصفية|فلتر|filter|cases|hearings|documents", "خيارات وفلاتر البحث")
        ])

        # 8. Intake & Retainers
        await check_route("استقطاب وتوقيع العقود (Intake)", "/intake", [
            (r"استقطاب|اتفاقية أتعاب|عقد|توكيل|intake", "عنوان استقطاب وتوقيع العقود"),
            (r"fee|amount|أتعاب|الدفعة|المبلغ", "حقول الأتعاب والمبالغ التعاقدية"),
            (r"signature|توقيع|sign", "منطقة التوقيع الإلكتروني")
        ])

        # 9. Yemeni Laws Library
        await check_route("مكتبة القوانين واللوائح اليمنية", "/yemeni-laws", [
            (r"القوانين واللوائح اليمنية|مكتبة تشريعات", "عنوان مكتبة التشريعات"),
            (r"رفع|مستند قانوني|قانون أو لائحة", "إضافة وتنزيل المستندات القانونية"),
            (r"البحث في التشريعات|ابحث بعنوان القانون", "البحث في نصوص التشريعات")
        ])

        # Also test Search AJAX query to verify no crashes
        search_ajax = await client.get("/search?q=شركة", cookies=cookies)
        results["استعلام البحث الفعلي (AJAX / Query)"] = {
            "path": "/search?q=شركة",
            "status": search_ajax.status_code,
            "missing": [],
            "found": [f"Status code {search_ajax.status_code}"],
            "has_500_or_error": search_ajax.status_code != 200
        }

    print("\n=== SUMMARY OF TESTS ===")
    all_ok = True
    for route, data in results.items():
        status_ok = data["status"] == 200
        no_missing = len(data["missing"]) == 0
        is_pass = status_ok and no_missing and not data["has_500_or_error"]
        if not is_pass:
            all_ok = False
        mark = "[PASS]" if is_pass else "[FAIL]"
        print(f"\n{mark} | {route} ({data['path']}) -> HTTP {data['status']}")
        for f in data["found"]:
            print(f"   [+] {f}")
        for m in data["missing"]:
            print(f"   [-] MISSING: {m}")

    return all_ok

if __name__ == "__main__":
    success = asyncio.run(run_full_suite())
    if not success:
        exit(1)
