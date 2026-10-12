import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_invoices_suite import test_invoices_full_suite
from tests.test_expenses_suite import test_expenses_full_suite
from tests.test_timesheets_suite import test_timesheets_full_suite
from tests.test_finance_suite import test_finance_full_suite

async def run_all_4_financial_suites():
    print("======================================================================")
    print("  RUNNING ALL 4 FINANCIAL & ACCOUNTING MODULE TEST SUITES (المالية والمحاسبة)")
    print("======================================================================")

    print("\n--- 1. Testing E-Invoicing Suite (/accounting/invoices) ---")
    await test_invoices_full_suite()
    print("[PASS] E-Invoicing Suite (الفوترة الإلكترونية) Passed 100%")

    print("\n--- 2. Testing Case Expenses Suite (/expenses) ---")
    await test_expenses_full_suite()
    print("[PASS] Case Expenses Suite (مصاريف القضية) Passed 100%")

    print("\n--- 3. Testing Timesheets Suite (/timesheet) ---")
    await test_timesheets_full_suite()
    print("[PASS] Timesheets Suite (سجل الساعات) Passed 100%")

    print("\n--- 4. Testing Accounts & Finance Suite (/finance) ---")
    await test_finance_full_suite()
    print("[PASS] Accounts & Finance Suite (الحسابات والمالية) Passed 100%")

    print("\n======================================================================")
    print("  ALL 4 FINANCIAL & ACCOUNTING SUITES PASSED WITH 100% SUCCESS!")
    print("======================================================================")

if __name__ == "__main__":
    asyncio.run(run_all_4_financial_suites())
