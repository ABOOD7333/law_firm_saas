"""Disabled legacy database dump utility.

This utility previously contained database passwords and exported personal and
legal records to a local text file. It must not be used. Create authorized,
encrypted backups through the database provider's supported backup workflow.
"""

raise SystemExit(
    "Disabled: use an authorized, encrypted database backup workflow."
)
