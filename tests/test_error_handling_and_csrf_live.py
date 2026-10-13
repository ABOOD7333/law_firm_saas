import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
from httpx import AsyncClient, ASGITransport
from main import app

async def run_error_and_csrf_tests():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        print("=== TEST 1: Login as R1990 ===")
        login_res = await client.post(
            "/",
            data={"email": "R1990", "password": "admin123456"},
            follow_redirects=False
        )
        assert login_res.status_code == 303, f"Login failed: {login_res.status_code}"
        cookies = dict(login_res.cookies)
        csrf_token = cookies.get("csrf_token", "")
        print(f"Login OK! CSRF Token: {csrf_token}")

        print("\n=== TEST 2: GET /clients and verify CSRF token in HTML ===")
        clients_page = await client.get("/clients", cookies=cookies)
        assert clients_page.status_code == 200
        assert 'name="csrf_token"' in clients_page.text
        print("GET /clients OK! Form contains csrf_token input.")

        print("\n=== TEST 3: Add Client with Valid CSRF Token ===")
        import secrets
        unique_phone = f"77{secrets.token_hex(3)}"
        valid_data = {
            "name": "موكل اختباري بنجاح",
            "client_type": "individual",
            "phone": unique_phone,
            "national_id": "100200300",
            "csrf_token": csrf_token
        }
        res_add = await client.post(
            "/clients/add",
            data=valid_data,
            cookies=cookies,
            follow_redirects=False
        )
        print(f"POST /clients/add Status: {res_add.status_code}")
        assert res_add.status_code == 303, f"Expected 303 redirect, got {res_add.status_code}: {res_add.text[:300]}"
        print("Add Client with valid CSRF succeeded 100%!")

        print("\n=== TEST 4: Add Client with Invalid/Missing CSRF (Verify Arabic Error Page) ===")
        invalid_csrf_data = {
            "name": "محاولة بدون رمز أمان",
            "phone": "770000000",
            "csrf_token": "invalid_or_expired_token"
        }
        res_csrf_fail = await client.post(
            "/clients/add",
            data=invalid_csrf_data,
            cookies=cookies,
            headers={"Accept": "text/html"},
            follow_redirects=False
        )
        print(f"POST /clients/add (Invalid CSRF) Status: {res_csrf_fail.status_code}")
        assert res_csrf_fail.status_code == 403
        # Verify it returns HTML with Arabic explanation, NOT raw black JSON!
        assert "text/html" in res_csrf_fail.headers.get("content-type", "")
        assert "رمز التحقق" in res_csrf_fail.text or "CSRF" in res_csrf_fail.text
        assert "تحديث الصفحة" in res_csrf_fail.text
        print("Verified: Invalid CSRF returns branded Arabic explanatory page instead of black JSON!")

        print("\n=== TEST 5: Verify 404 Route Returns Branded Arabic Error Page ===")
        res_404 = await client.get(
            "/this-route-does-not-exist-12345",
            cookies=cookies,
            headers={"Accept": "text/html"}
        )
        assert res_404.status_code == 404
        assert "text/html" in res_404.headers.get("content-type", "")
        assert "404" in res_404.text
        assert "الصفحة أو السجل غير موجود" in res_404.text
        print("Verified: 404 returns branded Arabic explanatory page!")

        print("\n=== TEST 6: Verify API Error Returns Clean Structured JSON ===")
        res_api_csrf = await client.post(
            "/clients/add",
            data=invalid_csrf_data,
            cookies=cookies,
            headers={"Accept": "application/json"},
            follow_redirects=False
        )
        assert res_api_csrf.status_code == 403
        json_data = res_api_csrf.json()
        assert json_data.get("success") is False
        assert "CSRF" in json_data.get("error", "") or "رمز" in json_data.get("error", "")
        print("Verified: API error returns structured JSON with clear Arabic error message!")

        print("\n=======================================================")
        print("ALL ERROR HANDLING & CSRF TESTS PASSED WITH 100% SUCCESS!")
        print("=======================================================")

if __name__ == "__main__":
    asyncio.run(run_error_and_csrf_tests())
