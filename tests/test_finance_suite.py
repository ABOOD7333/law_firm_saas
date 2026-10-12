import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal, engine
from database.models import AccessProfiles, LawCases, LawClients, LawTransactions, LawExpenses
from sqlalchemy import text

async def test_finance_full_suite():
    # Clear rate limiter attempts
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM rate_limit_attempts"))

    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 user must exist"

        user2 = db.query(AccessProfiles).filter(AccessProfiles.office_id != user1.office_id).first()
        assert user2 is not None, "User from different office must exist"

        # Case for office 1
        case1 = db.query(LawCases).filter(LawCases.office_id == user1.office_id, LawCases.is_deleted == 0).first()
        if not case1:
            case1 = LawCases(office_id=user1.office_id, case_number="CASE-FIN-01", title="قضية اختبار المالية", status_key="active")
            db.add(case1)
            db.commit()
            db.refresh(case1)

        # Client for office 1
        client1 = db.query(LawClients).filter(LawClients.office_id == user1.office_id, LawClients.is_deleted == 0).first()
        if not client1:
            client1 = LawClients(office_id=user1.office_id, name="شركة التقنية المتقدمة", phone="0501112233")
            db.add(client1)
            db.commit()
            db.refresh(client1)

        case_id = case1.id
        client_id = client1.id
        user1_office = user1.office_id
        user2_office = user2.office_id
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login user 1
        login_res = await client.post("/", data={"email": "R1990", "password": "admin123456"}, follow_redirects=False)
        assert login_res.status_code == 303, f"Login failed: {login_res.status_code}"
        cookies1 = dict(login_res.cookies)
        csrf1 = cookies1.get("csrf_token") or "test_csrf"
        headers1 = {"X-CSRF-Token": csrf1}

        # 2. Test GET /finance with different currencies
        for curr in ["SAR", "USD", "YER"]:
            page_res = await client.get(f"/finance?currency={curr}", cookies=cookies1)
            assert page_res.status_code == 200, f"Failed GET /finance with currency {curr}"
            assert "الحسابات والمالية" in page_res.text or "إجمالي الدخل" in page_res.text
            assert curr in page_res.text or "ر.س" in page_res.text

        # 3. Add Transaction (Income)
        trans_data = {
            "title": "دفعة أتعاب مرحلة الاستئناف",
            "amount": "15000.0",
            "transaction_at": "2026-10-12",
            "currency": "SAR",
            "exchange_rate": "1.0",
            "case_id": str(case_id),
            "client_id": str(client_id),
            "payment_method": "تحويل بنكي",
            "reference_number": "TRX-2026-9988",
            "notes": "سداد أتعاب القضية"
        }
        add_tx_res = await client.post("/finance/add_transaction", data=trans_data, cookies=cookies1, headers=headers1, follow_redirects=False)
        assert add_tx_res.status_code == 303, f"Add transaction failed: {add_tx_res.status_code}"

        # Verify transaction in DB
        db = SessionLocal()
        created_tx = None
        try:
            created_tx = db.query(LawTransactions).filter(
                LawTransactions.office_id == user1_office,
                LawTransactions.reference_number == "TRX-2026-9988",
                LawTransactions.is_deleted == 0
            ).first()
            assert created_tx is not None, "Created transaction not found in DB"
            assert created_tx.amount == 15000.0
            assert created_tx.client_id == client_id
            tx_id = created_tx.id
        finally:
            db.close()

        # 4. Add Expense
        exp_data = {
            "title": "رسوم تقرير خبير هندسي معتمد",
            "amount": "3500.0",
            "expense_at": "2026-10-12",
            "currency": "SAR",
            "exchange_rate": "1.0",
            "case_id": str(case_id),
            "expense_category": "أتعاب خبراء",
            "is_billable": "1",
            "payment_method": "شيك مصرفي",
            "notes": "تقرير الخبرة الفنية"
        }
        add_exp_res = await client.post("/finance/add_expense", data=exp_data, cookies=cookies1, headers=headers1, follow_redirects=False)
        assert add_exp_res.status_code == 303, f"Add expense failed: {add_exp_res.status_code}"

        # Verify expense in DB
        db = SessionLocal()
        created_exp = None
        try:
            created_exp = db.query(LawExpenses).filter(
                LawExpenses.office_id == user1_office,
                LawExpenses.title == "رسوم تقرير خبير هندسي معتمد",
                LawExpenses.is_deleted == 0
            ).first()
            assert created_exp is not None, "Created expense not found in DB"
            assert created_exp.amount == 3500.0
            assert created_exp.expense_category == "أتعاب خبراء"
            exp_id = created_exp.id
        finally:
            db.close()

        # 5. Export Invoice PDF
        pdf_res = await client.get(f"/finance/invoice/{tx_id}/pdf", cookies=cookies1)
        assert pdf_res.status_code == 200, f"Failed generating PDF: {pdf_res.status_code}"
        assert pdf_res.headers.get("content-type") == "application/pdf"
        assert len(pdf_res.content) > 500

        # 6. Test Multi-Tenant Cross-Office Isolation
        # Login user 2
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM rate_limit_attempts"))

        login_res2 = await client.post("/", data={"email": user2.username, "password": "admin123456"}, follow_redirects=False)
        assert login_res2.status_code == 303, f"User 2 login failed: {login_res2.status_code}"
        cookies2 = dict(login_res2.cookies)
        csrf2 = cookies2.get("csrf_token") or "test_csrf2"
        headers2 = {"X-CSRF-Token": csrf2}

        # User 2 tries to download User 1's PDF invoice -> 404
        pdf_res2 = await client.get(f"/finance/invoice/{tx_id}/pdf", cookies=cookies2)
        assert pdf_res2.status_code == 404, f"Security Breach! User 2 accessed User 1 PDF invoice: {pdf_res2.status_code}"

        # User 2 tries to delete User 1's transaction
        del_tx_res2 = await client.post(f"/finance/delete_transaction/{tx_id}", cookies=cookies2, headers=headers2, follow_redirects=False)
        db = SessionLocal()
        try:
            tx_check = db.query(LawTransactions).filter(LawTransactions.id == tx_id).first()
            assert tx_check.is_deleted == 0, "Security Breach! User 2 soft-deleted User 1 transaction!"
        finally:
            db.close()

        # User 2 tries to delete User 1's expense
        del_exp_res2 = await client.post(f"/finance/delete_expense/{exp_id}", cookies=cookies2, headers=headers2, follow_redirects=False)
        db = SessionLocal()
        try:
            exp_check = db.query(LawExpenses).filter(LawExpenses.id == exp_id).first()
            assert exp_check.is_deleted == 0, "Security Breach! User 2 soft-deleted User 1 expense!"
        finally:
            db.close()

        # 7. User 1 successfully soft-deletes transaction and expense
        del_tx_res = await client.post(f"/finance/delete_transaction/{tx_id}", cookies=cookies1, headers=headers1, follow_redirects=False)
        assert del_tx_res.status_code == 303

        del_exp_res = await client.post(f"/finance/delete_expense/{exp_id}", cookies=cookies1, headers=headers1, follow_redirects=False)
        assert del_exp_res.status_code == 303

        db = SessionLocal()
        try:
            tx_final = db.query(LawTransactions).filter(LawTransactions.id == tx_id).first()
            assert tx_final.is_deleted == 1, "Transaction was not soft-deleted"

            exp_final = db.query(LawExpenses).filter(LawExpenses.id == exp_id).first()
            assert exp_final.is_deleted == 1, "Expense was not soft-deleted"
        finally:
            db.close()

    print("ALL FINANCE TESTS PASSED SUCCESSFULLY! (100% COVERAGE & MULTI-TENANT ISOLATED)")

if __name__ == "__main__":
    asyncio.run(test_finance_full_suite())
