from typing import Optional, List
from sqlalchemy import Column, CheckConstraint, ForeignKey, Index, Integer, REAL, Table, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

# Junction table for Roles and Permissions
law_role_permissions = Table(
    'law_role_permissions',
    Base.metadata,
    Column('role_id', ForeignKey('law_roles.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', ForeignKey('law_permissions.id', ondelete='CASCADE'), primary_key=True)
)

class AccessProfiles(Base):
    __tablename__ = 'access_profiles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email_verified: Mapped[int] = mapped_column(Integer, CheckConstraint('email_verified IN (0, 1)'), nullable=False, server_default=text('0'))
    reset_verified: Mapped[int] = mapped_column(Integer, CheckConstraint('reset_verified IN (0, 1)'), nullable=False, server_default=text('0'))
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    protection_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'Ø±Ø¨Ø· Ø§Ù„Ø¬Ù‡Ø§Ø² Ø§Ù„Ø­Ø§Ù„ÙŠ'"))
    preferred_theme: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'light'"))
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'Ù…Ø­Ø§Ù…Ù�'"))
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'), index=True)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, CheckConstraint('is_active IN (0, 1)'), nullable=False, server_default=text('1'))
    can_view_all_cases: Mapped[int] = mapped_column(Integer, CheckConstraint('can_view_all_cases IN (0, 1)'), nullable=False, server_default=text('0'))
    is_2fa_enabled: Mapped[int] = mapped_column(Integer, CheckConstraint('is_2fa_enabled IN (0, 1)'), nullable=False, server_default=text('0'))
    age: Mapped[Optional[int]] = mapped_column(Integer)
    birth_date: Mapped[Optional[str]] = mapped_column(Text, index=True)
    device_fingerprint: Mapped[Optional[str]] = mapped_column(Text, index=True)
    device_name: Mapped[Optional[str]] = mapped_column(Text, index=True)
    security_question: Mapped[Optional[str]] = mapped_column(Text, index=True)
    last_login_at: Mapped[Optional[str]] = mapped_column(Text, index=True)
    last_login_device: Mapped[Optional[str]] = mapped_column(Text, index=True)
    access_pin_hash: Mapped[Optional[str]] = mapped_column(Text, index=True)
    office_id: Mapped[Optional[int]] = mapped_column(ForeignKey('law_offices.id'), index=True)
    role_id: Mapped[Optional[int]] = mapped_column(ForeignKey('law_roles.id'))
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id'))
    linked_owner_id: Mapped[Optional[int]] = mapped_column(Integer)
    job_title: Mapped[Optional[str]] = mapped_column(Text, index=True)
    username: Mapped[Optional[str]] = mapped_column(Text, index=True)
    lawyer_name: Mapped[Optional[str]] = mapped_column(Text, index=True)
    case_number: Mapped[Optional[str]] = mapped_column(Text, index=True)
    is_superadmin: Mapped[int] = mapped_column(Integer, CheckConstraint('is_superadmin IN (0, 1)'), nullable=False, server_default=text('0'))

    specializations: Mapped[List['LawSpecializations']] = relationship('LawSpecializations', secondary='law_user_specializations', back_populates='users')

class AuthVerificationTokens(Base):
    __tablename__ = 'auth_verification_tokens'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('access_profiles.id', ondelete='CASCADE'), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    token_type: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    consumed_at: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))

class AuthSessions(Base):
    __tablename__ = 'auth_sessions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('access_profiles.id', ondelete='CASCADE'), nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[int] = mapped_column(Integer, CheckConstraint('is_active IN (0, 1)'), nullable=False, server_default=text('1'))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, unique=True, index=True)

class AppSettings(Base):
    __tablename__ = 'app_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setting_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    setting_value: Mapped[Optional[str]] = mapped_column(Text, index=True)

class LawAuditLog(Base):
    __tablename__ = 'law_audit_log'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    action_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'), index=True)
    record_key: Mapped[Optional[str]] = mapped_column(Text, index=True)
    actor_name: Mapped[Optional[str]] = mapped_column(Text, index=True)
    details: Mapped[Optional[str]] = mapped_column(Text)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    office_id: Mapped[Optional[int]] = mapped_column(Integer)
    session_uuid: Mapped[Optional[str]] = mapped_column(Text)
    entity_type: Mapped[Optional[str]] = mapped_column(Text)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    old_values_json: Mapped[Optional[str]] = mapped_column(Text)
    new_values_json: Mapped[Optional[str]] = mapped_column(Text)
    device_context: Mapped[Optional[str]] = mapped_column(Text)

class LawCases(Base):
    __tablename__ = 'law_cases'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    case_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    case_type_key: Mapped[Optional[str]] = mapped_column(Text)
    status_key: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    visibility_mode: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'private'"))
    open_date: Mapped[Optional[str]] = mapped_column(Text)
    close_date: Mapped[Optional[str]] = mapped_column(Text)
    estimated_fee: Mapped[Optional[float]] = mapped_column(REAL, server_default=text('0'))
    claim_amount: Mapped[Optional[float]] = mapped_column(REAL, server_default=text('0'))
    lead_lawyer_id: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id'))
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id'))
    is_active: Mapped[int] = mapped_column(Integer, CheckConstraint('is_active IN (0, 1)'), nullable=False, server_default=text('1'))
    is_deleted: Mapped[int] = mapped_column(Integer, CheckConstraint('is_deleted IN (0, 1)'), nullable=False, server_default=text('0'))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    deleted_at: Mapped[Optional[str]] = mapped_column(Text)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))

    law_parties: Mapped[List['LawParties']] = relationship('LawParties', back_populates='law_case')
    law_hearings: Mapped[List['LawHearings']] = relationship('LawHearings', back_populates='law_case')
    law_documents: Mapped[List['LawDocuments']] = relationship('LawDocuments', back_populates='law_case')
    law_pleadings: Mapped[List['LawPleadings']] = relationship('LawPleadings', back_populates='law_case')
    law_judgments: Mapped[List['LawJudgments']] = relationship('LawJudgments', back_populates='law_case')
    law_transactions: Mapped[List['LawTransactions']] = relationship('LawTransactions', back_populates='law_case')
    law_tasks: Mapped[List['LawTasks']] = relationship('LawTasks', back_populates='law_case')
    law_executions: Mapped[List['LawExecutions']] = relationship('LawExecutions', back_populates='law_case')
    law_correspondences: Mapped[List['LawCorrespondences']] = relationship('LawCorrespondences', back_populates='law_case')
    law_notes: Mapped[List['LawNotes']] = relationship('LawNotes', back_populates='law_case')
    law_legal_references: Mapped[List['LawLegalReferences']] = relationship('LawLegalReferences', back_populates='law_case')
    law_limitations: Mapped[List['LawLimitations']] = relationship('LawLimitations', back_populates='law_case')
    law_power_of_attorneys: Mapped[List['LawPowerOfAttorney']] = relationship('LawPowerOfAttorney', back_populates='law_case')
    law_clients: Mapped[List['LawClients']] = relationship('LawClients', back_populates='law_case')
    law_expenses: Mapped[List['LawExpenses']] = relationship('LawExpenses', back_populates='law_case')
    law_timesheets: Mapped[List['LawTimesheets']] = relationship('LawTimesheets', back_populates='law_case')
    law_requests: Mapped[List['LawRequest']] = relationship('LawRequest', back_populates='law_case')

class LawClients(Base):
    __tablename__ = 'law_clients'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey('law_cases.id', ondelete='SET NULL'), index=True)
    case_number: Mapped[Optional[str]] = mapped_column(Text)
    office_id: Mapped[Optional[int]] = mapped_column(ForeignKey('law_offices.id'), index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(Text)
    alt_phone: Mapped[Optional[str]] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(Text)
    username: Mapped[Optional[str]] = mapped_column(Text)
    national_id: Mapped[Optional[str]] = mapped_column(Text)
    photo_path: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped[Optional['LawCases']] = relationship('LawCases', back_populates='law_clients')

class LawOffices(Base):
    __tablename__ = 'law_offices'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id'))
    status_key: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    subscription_plan: Mapped[str] = mapped_column(Text, server_default=text("'trial'"))
    subscription_end: Mapped[Optional[str]] = mapped_column(Text)
    receipt_base64: Mapped[Optional[str]] = mapped_column(Text)
    receipt_status: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[int] = mapped_column(Integer, CheckConstraint('is_active IN (0, 1)'), nullable=False, server_default=text('1'))
    is_deleted: Mapped[int] = mapped_column(Integer, CheckConstraint('is_deleted IN (0, 1)'), nullable=False, server_default=text('0'))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))

class LawParties(Base):
    __tablename__ = 'law_parties'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role_key: Mapped[str] = mapped_column(Text, nullable=False)
    id_number: Mapped[Optional[str]] = mapped_column(Text)
    phone: Mapped[Optional[str]] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(Text)
    address: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[int] = mapped_column(Integer, CheckConstraint('is_active IN (0, 1)'), nullable=False, server_default=text('1'))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_parties')

class LawHearings(Base):
    __tablename__ = 'law_hearings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    hearing_at: Mapped[str] = mapped_column(Text, nullable=False)
    next_hearing_date: Mapped[Optional[str]] = mapped_column(Text)
    status_key: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    result_summary: Mapped[Optional[str]] = mapped_column(Text)
    attachment_path: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_hearings')

class LawDocuments(Base):
    __tablename__ = 'law_documents'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    document_type_key: Mapped[str] = mapped_column(Text, nullable=False)
    doc_date: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_documents')

class LawPleadings(Base):
    __tablename__ = 'law_pleadings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    pleading_type_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[Optional[str]] = mapped_column(Text)
    version_no: Mapped[int] = mapped_column(Integer, server_default=text('1'))
    issue_date: Mapped[Optional[str]] = mapped_column(Text)
    status_key: Mapped[str] = mapped_column(Text, server_default=text("'draft'"))
    lead_lawyer_id: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id'))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_pleadings')

class LawJudgments(Base):
    __tablename__ = 'law_judgments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    judgment_date: Mapped[str] = mapped_column(Text, nullable=False)
    court_name: Mapped[Optional[str]] = mapped_column(Text)
    judge_name: Mapped[Optional[str]] = mapped_column(Text)
    status_key: Mapped[Optional[str]] = mapped_column(Text)
    judgment_text: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_judgments')

class LawTransactions(Base):
    __tablename__ = 'law_transactions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(REAL, nullable=False)
    transaction_at: Mapped[str] = mapped_column(Text, nullable=False)
    status_key: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)
    currency: Mapped[str] = mapped_column(Text, server_default=text("'SAR'"), nullable=False)
    exchange_rate: Mapped[float] = mapped_column(REAL, server_default=text('1.0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_transactions')

class LawTasks(Base):
    __tablename__ = 'law_tasks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey('law_cases.id', ondelete='SET NULL'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    due_at: Mapped[Optional[str]] = mapped_column(Text, index=True)
    assignee_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id'))
    status_key: Mapped[Optional[str]] = mapped_column(Text, server_default=text("'pending'"))
    priority_level: Mapped[int] = mapped_column(Integer, server_default=text('2'))
    is_active: Mapped[int] = mapped_column(Integer, CheckConstraint('is_active IN (0, 1)'), nullable=False, server_default=text('1'))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped[Optional['LawCases']] = relationship('LawCases', back_populates='law_tasks')

class LawExecutions(Base):
    __tablename__ = 'law_executions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    execution_number: Mapped[str] = mapped_column(Text, nullable=False)
    authority_name: Mapped[Optional[str]] = mapped_column(Text)
    status_key: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    request_date: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_executions')

class LawCorrespondences(Base):
    __tablename__ = 'law_correspondences'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    direction_key: Mapped[str] = mapped_column(Text, nullable=False)
    letter_number: Mapped[Optional[str]] = mapped_column(Text)
    letter_date: Mapped[Optional[str]] = mapped_column(Text)
    subject: Mapped[Optional[str]] = mapped_column(Text)
    auto_number: Mapped[Optional[str]] = mapped_column(Text)
    direction_seq: Mapped[Optional[int]] = mapped_column(Integer)
    response_status: Mapped[Optional[str]] = mapped_column(Text)
    needs_reply: Mapped[Optional[str]] = mapped_column(Text)
    reply_due_date: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_correspondences')

class LawNotes(Base):
    __tablename__ = 'law_notes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    note_type_key: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_notes')

class LawLegalReferences(Base):
    __tablename__ = 'law_legal_references'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    reference_url: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_legal_references')

class LawLimitations(Base):
    __tablename__ = 'law_limitations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    limitation_type_key: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[Optional[str]] = mapped_column(Text)
    due_date: Mapped[str] = mapped_column(Text, nullable=False)
    status_key: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_limitations')

class LawPowerOfAttorney(Base):
    __tablename__ = 'law_power_of_attorney'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    principal_name: Mapped[str] = mapped_column(Text, nullable=False)
    agency_number: Mapped[str] = mapped_column(Text, nullable=False)
    issue_date: Mapped[Optional[str]] = mapped_column(Text)
    expiry_date: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_power_of_attorneys')

class LawRoles(Base):
    __tablename__ = 'law_roles'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[int] = mapped_column(Integer, server_default=text('1'))

class LawPermissions(Base):
    __tablename__ = 'law_permissions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    permission_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

class LawDeviceLoginState(Base):
    __tablename__ = 'law_device_login_state'
    device_key: Mapped[str] = mapped_column(Text, primary_key=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    locked_until: Mapped[Optional[str]] = mapped_column(Text)
    last_failed_at: Mapped[Optional[str]] = mapped_column(Text)

class LawEmailNotificationLog(Base):
    __tablename__ = 'law_email_notification_log'
    __table_args__ = (
        UniqueConstraint('notification_type', 'target_email', 'reference_key'),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_email: Mapped[str] = mapped_column(Text, nullable=False)
    reference_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))

class LawExpenses(Base):
    __tablename__ = 'law_expenses'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(REAL, nullable=False)
    expense_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)
    currency: Mapped[str] = mapped_column(Text, server_default=text("'SAR'"), nullable=False)
    exchange_rate: Mapped[float] = mapped_column(REAL, server_default=text('1.0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_expenses')

class LawTimesheets(Base):
    __tablename__ = 'law_timesheets'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    duration_hours: Mapped[float] = mapped_column(REAL, server_default=text('0'))
    billable_rate: Mapped[float] = mapped_column(REAL, server_default=text('0'))
    user_id: Mapped[int] = mapped_column(ForeignKey('access_profiles.id'))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

    law_case: Mapped['LawCases'] = relationship('LawCases', back_populates='law_timesheets')

class LawReferenceData(Base):
    __tablename__ = 'law_reference_data'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id'), index=True)
    ref_type: Mapped[str] = mapped_column(Text, nullable=False)
    ref_name: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))

class LawSpecializations(Base):
    __tablename__ = 'law_specializations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    users: Mapped[List['AccessProfiles']] = relationship('AccessProfiles', secondary='law_user_specializations', back_populates='specializations')

class LawUserSpecializations(Base):
    __tablename__ = 'law_user_specializations'
    user_id: Mapped[int] = mapped_column(ForeignKey('access_profiles.id', ondelete='CASCADE'), primary_key=True)
    specialization_id: Mapped[int] = mapped_column(ForeignKey('law_specializations.id', ondelete='CASCADE'), primary_key=True)

class LawDeletedRecordArchive(Base):
    __tablename__ = 'law_deleted_record_archive'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    record_data: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_by: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id'))
    deleted_at: Mapped[str] = mapped_column(Text, server_default=text('CURRENT_TIMESTAMP'))

class LawNotificationLog(Base):
    __tablename__ = 'law_notification_log'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id', ondelete='CASCADE'))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    is_read: Mapped[int] = mapped_column(Integer, server_default=text('0'))
    created_at: Mapped[str] = mapped_column(Text, server_default=text('CURRENT_TIMESTAMP'))

class LawRequest(Base):
    __tablename__ = 'law_request'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    request_type: Mapped[str] = mapped_column(Text, nullable=False)
    request_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    priority_level: Mapped[Optional[str]] = mapped_column(Text)
    case_id: Mapped[int] = mapped_column(ForeignKey('law_cases.id', ondelete='CASCADE'), nullable=False)
    case_number: Mapped[Optional[str]] = mapped_column(Text)
    entity_name: Mapped[Optional[str]] = mapped_column(Text)
    source_office_id: Mapped[Optional[int]] = mapped_column(ForeignKey('law_offices.id'))
    target_office_id: Mapped[Optional[int]] = mapped_column(ForeignKey('law_offices.id'))
    requested_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id'))
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id'))
    reason_text: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    deleted_at: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    deleted_by_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))

    law_case: Mapped[Optional['LawCases']] = relationship('LawCases', back_populates='law_requests')
    approvals: Mapped[List['LawRequestApproval']] = relationship('LawRequestApproval', back_populates='request', cascade='all, delete-orphan')
    receipts: Mapped[List['LawRequestReceipt']] = relationship('LawRequestReceipt', back_populates='request', cascade='all, delete-orphan')

class LawRequestApproval(Base):
    __tablename__ = 'law_request_approval'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey('law_request.id', ondelete='CASCADE'), nullable=False)
    approval_step_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    approval_level_name: Mapped[Optional[str]] = mapped_column(Text)
    approval_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id'))
    approval_notes: Mapped[Optional[str]] = mapped_column(Text)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    approved_at: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    deleted_at: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    deleted_by_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))

    request: Mapped['LawRequest'] = relationship('LawRequest', back_populates='approvals')

class LawRequestReceipt(Base):
    __tablename__ = 'law_request_receipt'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey('law_request.id', ondelete='CASCADE'), nullable=False)
    receipt_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    receipt_notes: Mapped[Optional[str]] = mapped_column(Text)
    received_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id'))
    received_at: Mapped[Optional[str]] = mapped_column(Text)
    execution_result: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    deleted_at: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    deleted_by_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))

    request: Mapped['LawRequest'] = relationship('LawRequest', back_populates='receipts')

class LawTemplates(Base):
    __tablename__ = 'law_templates'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id', ondelete='CASCADE'), index=True)
    template_key: Mapped[str] = mapped_column(Text, nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)

class LawWorkflowRules(Base):
    __tablename__ = 'law_workflow_rules'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_key: Mapped[str] = mapped_column(Text, nullable=False)  # 'on_hearing_created' | 'on_case_limitation_warning'
    action_type: Mapped[str] = mapped_column(Text, nullable=False)  # 'create_task'
    action_config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON configuration
    is_active: Mapped[int] = mapped_column(Integer, CheckConstraint('is_active IN (0, 1)'), nullable=False, server_default=text('1'))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)

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


# ===================================================
# ÌÏÇæá ÇáãÓÇÚÏ ÇáÐßí ÇáÞÇäæäí
# ===================================================

class AIChatHistory(Base):
    __tablename__ = 'ai_chat_history'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('access_profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    intent_type: Mapped[Optional[str]] = mapped_column(Text, index=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'), index=True)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)


class AIKnowledge(Base):
    __tablename__ = 'ai_knowledge'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id', ondelete='CASCADE'), nullable=False, index=True)
    category: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey('access_profiles.id'), nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'), index=True)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)

# ===================================================
# ÌÏÇæá ãÍÑß ÇáãÚÑÝÉ RAG (ÇáãÑÍáÉ ÇáËÇäíÉ)
# ===================================================

class KnowledgeDocument(Base):
    __tablename__ = 'rag_knowledge_documents'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id', ondelete='CASCADE'), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False) # pdf, docx, txt, img
    category: Mapped[str] = mapped_column(Text, nullable=False, index=True) # ÇáÞÓã ÇáÞÇäæäí
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'")) # pending, indexing, indexed, failed
    document_hash: Mapped[str] = mapped_column(Text, unique=True, index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, server_default=text('0'))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey('access_profiles.id'), nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'), index=True)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[int] = mapped_column(Integer, server_default=text('0'), nullable=False)


class DocumentChunkMetadata(Base):
    __tablename__ = 'rag_chunk_metadata'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('rag_knowledge_documents.id', ondelete='CASCADE'), nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True) # ID in Vector DB
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    article_number: Mapped[Optional[str]] = mapped_column(Text)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))


# ============================================================
# Payment Requests — طلبات الدفع بالتحويل البنكي
# ============================================================
class PaymentRequest(Base):
    __tablename__ = 'payment_requests'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('access_profiles.id', ondelete='SET NULL'), nullable=True)
    plan: Mapped[str] = mapped_column(Text, nullable=False)           # 'monthly' | 'yearly'
    amount: Mapped[Optional[float]] = mapped_column(REAL)             # المبلغ المدفوع
    currency: Mapped[str] = mapped_column(Text, server_default=text("'USD'"))
    transfer_ref: Mapped[Optional[str]] = mapped_column(Text)         # رقم مرجع التحويل
    receipt_base64: Mapped[Optional[str]] = mapped_column(Text)       # صورة الإيصال
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))  # pending|approved|rejected
    admin_notes: Mapped[Optional[str]] = mapped_column(Text)          # ملاحظات الأدمن
    submitted_at: Mapped[str] = mapped_column(Text, server_default=text('CURRENT_TIMESTAMP'))
    reviewed_at: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer)

