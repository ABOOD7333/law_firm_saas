import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal
from database.models import LawClients, LawCases, LawHearings, LawParties, LawDocuments

async def test_crud_suite():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login with R1990
        login_resp = await client.post(
            "/",
            data={"email": "R1990", "password": "admin123456"},
            follow_redirects=False
        )
        assert login_resp.status_code == 303, f"Login failed: {login_resp.status_code}"
        cookies = dict(login_resp.cookies)
        csrf_token = cookies.get("csrf_token", "")
        headers = {"X-CSRF-Token": csrf_token}

        print("=== Test 1: Add New Client (POST /clients/add) ===")
        client_phone = "0501112233"
        # Check if already exists from prior run or cleanup
        db = SessionLocal()
        existing_client = db.query(LawClients).filter(LawClients.phone == client_phone).first()
        if existing_client:
            client_id = existing_client.id
            print(f"Using existing client ID: {client_id}")
        else:
            client_data = {
                "name": "شركة التقنية المتقدمة للاختبار",
                "phone": client_phone,
                "email": "tech_test@example.com",
                "client_type": "company",
                "cr_number": "1010998877",
                "legal_rep_name": "سعد المطيري",
                "national_id": "1098765432",
                "city": "الرياض",
                "address": "طريق الملك فهد",
                "notes": "موكل اختباري للتحقق من سلامة الحقول",
                "portal_access": "1",
                "portal_password": "ClientPassword123"
            }
            res_client = await client.post("/clients/add", data=client_data, cookies=cookies, headers=headers)
            print(f"Client Add Status: {res_client.status_code}")
            assert res_client.status_code in [200, 302, 303], f"Unexpected status {res_client.status_code}"

            created_client = db.query(LawClients).filter(LawClients.phone == client_phone).first()
            assert created_client is not None, "Client was not saved in DB"
            client_id = created_client.id
            print(f"Created Client ID: {client_id}")

        print("\n=== Test 2: Add New Case (POST /cases/add) ===")
        case_number = f"TEST-CASE-{client_id}-99"
        existing_case = db.query(LawCases).filter(LawCases.case_number == case_number).first()
        if existing_case:
            case_id = existing_case.id
            print(f"Using existing case ID: {case_id}")
        else:
            case_data = {
                "title": "دعوى مطالبة مالية - اختبار أوتوماتيكي",
                "case_number": case_number,
                "client_id": str(client_id),
                "court_name": "المحكمة التجارية بالرياض",
                "case_type": "تجاري",
                "case_type_key": "commercial",
                "status_key": "active",
                "notes": "قضية اختبارية"
            }
            res_case = await client.post("/cases/add", data=case_data, cookies=cookies, headers=headers)
            print(f"Case Add Status: {res_case.status_code}")
            assert res_case.status_code in [200, 302, 303], f"Unexpected status {res_case.status_code}"

            created_case = db.query(LawCases).filter(LawCases.case_number == case_number).first()
            assert created_case is not None, "Case was not saved in DB"
            case_id = created_case.id
            print(f"Created Case ID: {case_id}")

        print("\n=== Test 3: Add New Party (POST /parties/add) ===")
        party_data = {
            "case_id": str(case_id),
            "name": "شركة المقاولات المتحدة (خصم)",
            "role_key": "defendant",
            "party_type": "company",
            "phone": "0555112233",
            "id_number": "7001234567",
            "lawyer_name": "عبدالله المحامي",
            "conflict_status": "clear",
            "internal_notes": "الطرف المدعى عليه"
        }
        res_party = await client.post("/parties/add", data=party_data, cookies=cookies, headers=headers)
        print(f"Party Add Status: {res_party.status_code}")
        assert res_party.status_code in [200, 302, 303], f"Unexpected status {res_party.status_code}"

        created_party = db.query(LawParties).filter(LawParties.case_id == case_id).first()
        assert created_party is not None, "Party was not saved in DB"
        print(f"Created Party ID: {created_party.id}")

        print("\n=== Test 4: Add New Hearing (POST /hearings/add) ===")
        hearing_data = {
            "case_id": str(case_id),
            "title": "جلسة المرافعة الأولى",
            "hearing_at": "2026-11-15T10:00",
            "status_key": "scheduled",
            "decision": "تأجيل الجلسة لتبادل المذكرات",
            "lawyer_notes": "تم حضور وكيل المدعي والمدعى عليه"
        }
        res_hearing = await client.post("/hearings/add", data=hearing_data, cookies=cookies, headers=headers)
        print(f"Hearing Add Status: {res_hearing.status_code}")
        assert res_hearing.status_code in [200, 302, 303], f"Unexpected status {res_hearing.status_code}"

        created_hearing = db.query(LawHearings).filter(LawHearings.case_id == case_id).first()
        assert created_hearing is not None, "Hearing was not saved in DB"
        print(f"Created Hearing ID: {created_hearing.id}")

        print("\n=== Test 5: Save Contract Analysis Report (POST /api/contract-analyzer/save-report) ===")
        report_data = {
            "case_id": str(case_id),
            "contract_title": "عقد توريد تجاري اختباري",
            "report_content": "تقرير فحص المخاطر القانونية: العقد يتضمن بنود إعفاء غير مقبولة نظاماً، ويجب إضافة بند التحكيم.",
            "risk_level": "عالي"
        }
        res_report = await client.post(
            "/api/contract-analyzer/save-report",
            data=report_data,
            cookies=cookies,
            headers=headers
        )
        print(f"Contract Report Save Status: {res_report.status_code}")
        assert res_report.status_code == 200, f"Unexpected status {res_report.status_code}"
        report_json = res_report.json()
        print("Report Save Response:", report_json)
        assert report_json.get("success") is True, "Report save failed"

        # Verify document was created in DB
        saved_doc = db.query(LawDocuments).filter(LawDocuments.case_id == case_id).first()
        assert saved_doc is not None, "Document not created in DB"
        print(f"Created Document in DMS: ID={saved_doc.id}, Name={saved_doc.name}")

        db.close()
        print("\n=== ALL 5 FUNCTIONAL CRUD WORKFLOWS PASSED WITH 100% SUCCESS ===")

if __name__ == "__main__":
    asyncio.run(test_crud_suite())
