"""Legacy database inspection script intentionally disabled.

The previous version embedded a production database connection string. Do not
put credentials in source code; use the Railway dashboard's database tools.
"""

raise SystemExit(
    "This script is disabled because database credentials must never be stored in source code."
)
