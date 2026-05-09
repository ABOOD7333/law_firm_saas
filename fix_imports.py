"""
سكريبت تلقائي لإصلاح wildcard imports في جميع الـ routers.
يستبدل: from database.models import *
بـ:     from database.models import <القائمة الفعلية للنماذج المستخدمة>
"""
import re, os

ALL_MODELS = [
    "AccessProfiles", "AuthSessions", "AuthVerificationTokens", "AppSettings",
    "LawAuditLog", "LawCases", "LawClients", "LawOffices", "LawParties",
    "LawHearings", "LawDocuments", "LawPleadings", "LawJudgments",
    "LawTransactions", "LawTasks", "LawExecutions", "LawCorrespondences",
    "LawNotes", "LawLegalReferences", "LawLimitations", "LawPowerOfAttorney",
    "LawRoles", "LawPermissions", "LawDeviceLoginState", "LawEmailNotificationLog",
    "LawExpenses", "LawTimesheets", "LawReferenceData", "LawSpecializations",
    "LawUserSpecializations", "LawDeletedRecordArchive", "LawNotificationLog",
    "LawRequest", "LawRequestApproval", "LawRequestReceipt",
]

ROUTERS_DIR = r"c:\Users\Roots\Desktop\law_firm1\routers"
WILDCARD_PAT = re.compile(r"from database\.models import \*")

fixed = 0
for fname in os.listdir(ROUTERS_DIR):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(ROUTERS_DIR, fname)
    with open(fpath, encoding="utf-8") as f:
        content = f.read()

    if "from database.models import *" not in content:
        continue

    used = [m for m in ALL_MODELS if re.search(rf"\b{m}\b", content)]

    if not used:
        replacement = "from database.models import Base"
    elif len(used) <= 3:
        replacement = f"from database.models import {', '.join(used)}"
    else:
        joined = ",\n    ".join(used)
        replacement = f"from database.models import (\n    {joined}\n)"

    new_content = WILDCARD_PAT.sub(replacement, content)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"  OK {fname}: {len(used)} models")
    fixed += 1

print(f"\nFixed {fixed} files.")
