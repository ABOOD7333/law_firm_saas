import re

with open("database/models.py", "r", encoding="utf-8") as f:
    content = f.read()

# Tables to add updated_at and is_deleted
targets = [
    "class AccessProfiles(Base):",
    "class LawClients(Base):",
    "class LawParties(Base):",
    "class LawHearings(Base):",
    "class LawDocuments(Base):",
    "class LawPleadings(Base):",
    "class LawJudgments(Base):",
    "class LawTransactions(Base):",
    "class LawTasks(Base):",
    "class LawExecutions(Base):",
    "class LawCorrespondences(Base):",
    "class LawNotes(Base):",
    "class LawLegalReferences(Base):",
    "class LawLimitations(Base):",
    "class LawPowerOfAttorney(Base):",
    "class LawExpenses(Base):",
    "class LawTimesheets(Base):"
]

for target in targets:
    # Find the class and append columns right before the relationships or at the end of the class body
    # A simple way is to find the last column definition and insert there
    # But since each class has a `created_at` column, we can replace `created_at: Mapped...` with
    # `created_at: Mapped... \n    updated_at: Mapped[Optional[str]] = mapped_column(Text)\n    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)`
    
    # Wait, some tables already have created_at, let's find the class scope.
    class_pattern = re.compile(rf"{re.escape(target)}.*?(?=class |\Z)", re.DOTALL)
    match = class_pattern.search(content)
    if match:
        class_body = match.group(0)
        if "updated_at: Mapped[" not in class_body:
            # Insert after created_at
            if "created_at:" in class_body:
                new_class_body = re.sub(
                    r"(created_at: Mapped\[.*?\] = mapped_column\(.*?\))",
                    r"\1\n    updated_at: Mapped[Optional[str]] = mapped_column(Text)\n    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)",
                    class_body
                )
                content = content.replace(class_body, new_class_body)

# Update AuthSessions
auth_session_pattern = re.compile(r"(class AuthSessions\(Base\):.*?)(?=\nclass |\Z)", re.DOTALL)
match = auth_session_pattern.search(content)
if match:
    auth_body = match.group(1)
    if "refresh_token:" not in auth_body:
        new_auth_body = auth_body.replace(
            "expires_at: Mapped[str] = mapped_column(Text, nullable=False)",
            "expires_at: Mapped[str] = mapped_column(Text, nullable=False)\n    refresh_token: Mapped[Optional[str]] = mapped_column(Text, unique=True, index=True)"
        )
        content = content.replace(auth_body, new_auth_body)

# Add LawUserDevices table
if "class LawUserDevices" not in content:
    devices_model = """
class LawUserDevices(Base):
    __tablename__ = 'law_user_devices'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('access_profiles.id', ondelete='CASCADE'), nullable=False)
    device_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    fcm_token: Mapped[Optional[str]] = mapped_column(Text)
    biometric_public_key: Mapped[Optional[str]] = mapped_column(Text)
    device_name: Mapped[Optional[str]] = mapped_column(Text)
    last_active: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[int] = mapped_column(Integer, server_default=text('1'), nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    user: Mapped['AccessProfiles'] = relationship('AccessProfiles')
"""
    content += devices_model

with open("database/models.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Models patched successfully.")
