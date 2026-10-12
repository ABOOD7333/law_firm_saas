import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.database import engine
from sqlalchemy import text

def clear_rate_limits():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM rate_limit_attempts"))

async def run_all():
    print("=" * 60)
    print("RUNNING ALL 7 PROCEDURAL & COURT INTERFACES TEST SUITES")
    print("=" * 60)

    # 1. Tasks & Kanban
    clear_rate_limits()
    print("\n>>> SUITE 1/7: Tasks & Kanban (/tasks, /kanban)")
    from tests.test_tasks_suite import test_tasks_and_kanban_flow
    await test_tasks_and_kanban_flow()

    # 2. Calendar
    clear_rate_limits()
    print("\n>>> SUITE 2/7: Court Calendar (/calendar)")
    from tests.test_calendar_suite import test_calendar_flow
    await test_calendar_flow()

    # 3. Executions
    clear_rate_limits()
    print("\n>>> SUITE 3/7: Executions (/execution)")
    from tests.test_executions_suite import test_executions_flow
    await test_executions_flow()

    # 4. Power of Attorney
    clear_rate_limits()
    print("\n>>> SUITE 4/7: Power of Attorney (/power_of_attorney)")
    from tests.test_poa_suite import test_poa_flow
    await test_poa_flow()

    # 5. Timeline
    clear_rate_limits()
    print("\n>>> SUITE 5/7: Case Timeline (/timeline)")
    from tests.test_timeline_suite import test_timeline_flow
    await test_timeline_flow()

    # 6. Limitations
    clear_rate_limits()
    print("\n>>> SUITE 6/7: Limitations & Deadlines (/limitations)")
    from tests.test_limitations_suite import test_limitations_full_suite
    await test_limitations_full_suite()

    # 7. Legal References
    clear_rate_limits()
    print("\n>>> SUITE 7/7: Legal References (/legal_references)")
    from tests.test_legal_references_suite import test_legal_references_full_suite
    await test_legal_references_full_suite()

    print("\n" + "=" * 60)
    print("ALL 7 PROCEDURAL & COURT INTERFACES TEST SUITES PASSED 100%!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_all())
