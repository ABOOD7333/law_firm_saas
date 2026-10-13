import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
from httpx import AsyncClient, ASGITransport
from main import app

async def test_all_ui_pages():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as R1990
        login_res = await client.post(
            "/",
            data={"email": "R1990", "password": "admin123456"},
            follow_redirects=False
        )
        cookies = dict(login_res.cookies)
        print(f"Login status: {login_res.status_code}")
        if login_res.status_code != 303:
            print("Login failed! Response body:", login_res.text[:300])
            return

        # List of all GET UI routes to test
        routes_to_test = [
            ("/", "Dashboard Root"),
            ("/dashboard", "Dashboard Direct"),
            ("/clients", "Clients"),
            ("/cases", "Cases"),
            ("/parties", "Parties"),
            ("/hearings", "Hearings"),
            ("/documents", "Documents"),
            ("/pleadings", "Pleadings"),
            ("/judgments", "Judgments"),
            ("/notes", "Notes"),
            ("/correspondences", "Correspondences"),
            ("/tasks", "Tasks"),
            ("/kanban", "Kanban"),
            ("/calendar", "Calendar"),
            ("/execution", "Execution"),
            ("/power_of_attorney", "Power of Attorney"),
            ("/timeline", "Timeline"),
            ("/limitations", "Limitations"),
            ("/legal_references", "Legal References"),
            ("/accounting/invoices", "Invoices"),
            ("/expenses", "Expenses"),
            ("/timesheet", "Timesheet"),
            ("/finance", "Finance"),
            ("/reports", "Reports"),
            ("/yemeni-laws", "Yemeni Laws Library"),
            ("/settings", "Settings"),
            ("/team", "Team"),
            ("/subscription", "Subscription"),
            ("/reference_data", "Reference Data"),
            ("/search?q=test", "Search"),
            ("/activity", "Activity Log"),
            ("/client-portal", "Client Portal"),
            ("/automation", "Automation"),
            ("/advanced_operations", "Advanced Operations")
        ]

        results = []
        errors = []

        print(f"\nTesting {len(routes_to_test)} UI routes live...")
        print("=" * 65)

        for route, name in routes_to_test:
            try:
                res = await client.get(route, cookies=cookies, follow_redirects=True)
                status = res.status_code
                
                # Check for 500 error or exception trace in HTML
                has_error = (status >= 400) or ("Internal Server Error" in res.text) or ("Traceback" in res.text)
                
                if has_error:
                    errors.append((name, route, status, res.text[:200]))
                    print(f"[FAIL] {name:25} ({route:25}) -> Status: {status}")
                else:
                    results.append((name, route, status))
                    print(f"[PASS] {name:25} ({route:25}) -> Status: {status}")
            except Exception as e:
                errors.append((name, route, "EXCEPTION", str(e)))
                print(f"[EXCP] {name:25} ({route:25}) -> Error: {e}")

        print("=" * 65)
        print(f"Total Tested: {len(routes_to_test)}")
        print(f"Passed: {len(results)}")
        print(f"Failed: {len(errors)}")

        if errors:
            print("\nFailures Detail:")
            for err in errors:
                print(f"  - {err[0]} ({err[1]}): {err[2]} | {err[3]}")
        else:
            print("\nALL TESTED UI PAGES LOADED SUCCESSFULLY WITH ZERO 500 ERRORS!")

if __name__ == "__main__":
    asyncio.run(test_all_ui_pages())
