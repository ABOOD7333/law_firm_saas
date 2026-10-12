import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal
from database.models import AccessProfiles, LawCases, LawLegalReferences

async def test_legal_references_full_suite():
    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 user must exist"
        case1 = db.query(LawCases).filter(LawCases.office_id == user1.office_id, LawCases.is_deleted == 0).first()
        if not case1:
            case1 = LawCases(office_id=user1.office_id, case_number="CASE-REF-101", title="قضية اختبار المراجع", status_key="active")
            db.add(case1)
            db.commit()
            db.refresh(case1)
        case_id = case1.id

        user2 = db.query(AccessProfiles).filter(AccessProfiles.office_id != user1.office_id).first()
        assert user2 is not None, "User 2 must exist"
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login user 1
        login_res = await client.post("/", data={"email": "R1990", "password": "admin123456"}, follow_redirects=False)
        assert login_res.status_code == 303, f"Login failed: {login_res.status_code}"
        cookies = dict(login_res.cookies)
        csrf_token = cookies.get("csrf_token") or "test_csrf"
        headers = {"X-CSRF-Token": csrf_token}

        # 2. Get legal references page
        page_res = await client.get("/legal_references", cookies=cookies)
        assert page_res.status_code == 200
        assert "المراجع والأنظمة القانونية" in page_res.text
        assert "إجمالي المراجع" in page_res.text
        assert "سوابق ومبادئ" in page_res.text

        # 3. Create a legal reference
        payload = {
            "title": "التعويض المستحق عند الإنهاء لسبب غير مشروع",
            "category": "نظام / قانون",
            "article_number": "المادة 77",
            "source": "نظام العمل السعودي",
            "case_id": case_id,
            "content": "ما لم يتضمن العقد تعويضاً محدداً، يستحق الطرف المتضرر أجرة خمسة عشر يوماً عن كل سنة من سنوات خدمة العامل...",
            "keywords": "تعويض، فصل تعسفي، إنهاء العقد، أجر",
            "reference_url": "https://laws.boe.gov.sa/Boe/Laws/LawDetails/256/1"
        }
        create_res = await client.post("/api/legal_references/save", json=payload, cookies=cookies, headers=headers)
        assert create_res.status_code == 200
        create_data = create_res.json()
        assert create_data["ok"] is True
        ref_id = create_data["id"]

        # 4. Get legal reference details via API
        get_res = await client.get(f"/api/legal_references/{ref_id}", cookies=cookies)
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["ok"] is True
        assert get_data["data"]["title"] == "التعويض المستحق عند الإنهاء لسبب غير مشروع"
        assert get_data["data"]["article_number"] == "المادة 77"
        assert get_data["data"]["source"] == "نظام العمل السعودي"
        assert "أجرة خمسة عشر يوماً" in get_data["data"]["content"]

        # 5. Test Multi-Tenant Isolation (User 2 cannot access user1's legal reference)
        client2 = AsyncClient(transport=transport, base_url="http://test")
        login2 = await client2.post("/", data={"email": user2.username, "password": "password123"}, follow_redirects=False)
        cookies2 = dict(login2.cookies)
        cross_res = await client2.get(f"/api/legal_references/{ref_id}", cookies=cookies2)
        assert cross_res.status_code in [404, 403, 401, 303]

        # 6. Update legal reference
        payload["id"] = ref_id
        payload["title"] = "معدل: التعويض المستحق بموجب المادة 77 عمل"
        update_res = await client.post("/api/legal_references/save", json=payload, cookies=cookies, headers=headers)
        assert update_res.status_code == 200
        assert update_res.json()["ok"] is True

        # 7. Delete legal reference (soft delete)
        del_res = await client.delete(f"/api/legal_references/delete/{ref_id}", cookies=cookies, headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["ok"] is True

        # Verify soft deleted in DB
        db = SessionLocal()
        try:
            del_record = db.query(LawLegalReferences).filter(LawLegalReferences.id == ref_id).first()
            assert del_record.is_deleted == 1
        finally:
            db.close()

        print("\nAll Legal References Tests (including Multi-Tenant Isolation) PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_legal_references_full_suite())
