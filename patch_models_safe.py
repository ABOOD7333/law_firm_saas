import re

with open("database/models.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

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

in_target = False
target_indent = ""
new_lines = []

for i, line in enumerate(lines):
    new_lines.append(line)
    
    # Check if we are starting a target class
    for t in targets:
        if line.startswith(t):
            in_target = True
            break
            
    if in_target:
        # Check if line contains created_at
        if "created_at: Mapped[" in line:
            # We found created_at inside a target class, now append the new columns
            # Get the indentation of the created_at line
            indent = line[:len(line) - len(line.lstrip())]
            new_lines.append(indent + "updated_at: Mapped[Optional[str]] = mapped_column(Text)\n")
            new_lines.append(indent + "is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)\n")
            in_target = False

# Now handle AuthSessions
auth_in_target = False
final_lines = []
for line in new_lines:
    final_lines.append(line)
    if line.startswith("class AuthSessions(Base):"):
        auth_in_target = True
    if auth_in_target and "expires_at: Mapped[" in line:
        indent = line[:len(line) - len(line.lstrip())]
        final_lines.append(indent + "refresh_token: Mapped[Optional[str]] = mapped_column(Text, unique=True, index=True)\n")
        auth_in_target = False

content = "".join(final_lines)

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
