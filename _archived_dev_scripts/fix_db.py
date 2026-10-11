"""Legacy production database repair script intentionally disabled.

This file previously embedded a live database credential and could mutate the
production schema. Use reviewed Alembic migrations with an authorized operator.
"""

raise SystemExit("This script is disabled. Use the reviewed Alembic migration workflow.")
