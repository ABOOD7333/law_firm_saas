"""Regression tests for high-risk authorization and encrypted conflict checks."""
import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from core.conflict_checker import perform_conflict_check
from core.security import hash_session_token
from database.database import SessionLocal
from database.models import (
    AccessProfiles,
    AuthSessions,
    LawCases,
    LawClients,
    LawOffices,
    LawPowerOfAttorney,
)
from dependencies import check_user_permission, get_current_user
from routers.client_portal import client_sign_poa


def _request(token: str, extra_cookies: str = "") -> Request:
    cookie = f"session_token={token}"
    if extra_cookies:
        cookie += "; " + extra_cookies
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/dashboard",
        "raw_path": b"/dashboard",
        "query_string": b"",
        "headers": [(b"cookie", cookie.encode())],
        "server": ("test", 80),
        "client": ("127.0.0.1", 12345),
    })


def _create_client_user(db, username: str, *, phone: str, email: str):
    user = AccessProfiles(
        name="موكل اختبار",
        username=username,
        phone=phone,
        email=email,
        role="موكل",
        office_id=1,
        is_active=1,
        is_deleted=0,
    )
    db.add(user)
    db.flush()
    return user


def test_support_cookie_alone_does_not_grant_support_permissions():
    db = SessionLocal()
    username = "ci-cookie-" + uuid.uuid4().hex[:12]
    token = uuid.uuid4().hex
    user = None
    session = None
    try:
        user = _create_client_user(
            db,
            username,
            phone="+9665" + uuid.uuid4().hex[:9],
            email=f"{username}@example.test",
        )
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        session = AuthSessions(
            session_token=hash_session_token(token),
            user_id=user.id,
            device_id=None,
            is_active=1,
            expires_at=expires,
        )
        db.add(session)
        db.commit()

        current = get_current_user(_request(token, "is_support_session=1"), db)

        assert current is not None
        assert current.is_support_session is False
        assert check_user_permission(current, "team", "manage") is False
    finally:
        if session is not None:
            db.query(AuthSessions).filter(AuthSessions.id == session.id).delete()
        if user is not None:
            db.query(AccessProfiles).filter(AccessProfiles.id == user.id).delete()
        db.commit()
        db.close()


def test_server_marked_impersonation_session_keeps_support_access():
    db = SessionLocal()
    username = "ci-support-" + uuid.uuid4().hex[:12]
    token = uuid.uuid4().hex
    user = None
    session = None
    try:
        user = _create_client_user(
            db,
            username,
            phone="+9665" + uuid.uuid4().hex[:9],
            email=f"{username}@example.test",
        )
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        session = AuthSessions(
            session_token=hash_session_token(token),
            user_id=user.id,
            device_id="impersonated_by_admin_999",
            is_active=1,
            expires_at=expires,
        )
        db.add(session)
        db.commit()

        current = get_current_user(_request(token), db)

        assert current is not None
        assert current.is_support_session is True
        assert check_user_permission(current, "team", "manage") is True
    finally:
        if session is not None:
            db.query(AuthSessions).filter(AuthSessions.id == session.id).delete()
        if user is not None:
            db.query(AccessProfiles).filter(AccessProfiles.id == user.id).delete()
        db.commit()
        db.close()


def test_client_cannot_sign_poa_for_another_client_case():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    user = other_case = own_case = client = poa = None
    try:
        own_case = LawCases(
            office_id=1,
            case_number=f"CI-POA-OWN-{suffix}",
            title="قضية الموكل الاختباري",
            is_deleted=0,
        )
        other_case = LawCases(
            office_id=1,
            case_number=f"CI-POA-OTHER-{suffix}",
            title="قضية موكل آخر",
            is_deleted=0,
        )
        db.add_all([own_case, other_case])
        db.flush()

        user = _create_client_user(
            db,
            f"ci-poa-{suffix}",
            phone=f"+9665{suffix[:9]}",
            email=f"poa-{suffix}@example.test",
        )
        client = LawClients(
            office_id=1,
            user_id=user.id,
            case_id=own_case.id,
            name=f"موكل {suffix}",
            phone=user.phone,
            email=user.email,
            is_deleted=0,
        )
        poa = LawPowerOfAttorney(
            office_id=1,
            case_id=other_case.id,
            principal_name=f"موكل آخر {suffix}",
            agency_number=f"CI-POA-{suffix}",
            is_deleted=0,
        )
        db.add_all([client, poa])
        db.commit()

        with pytest.raises(HTTPException) as error:
            asyncio.run(client_sign_poa(
                poa_id=poa.id,
                request=_request("unused"),
                data={"signature": "not-used"},
                db=db,
                user=user,
            ))
        assert error.value.status_code == 403
    finally:
        db.rollback()
        if poa is not None and poa.id:
            db.query(LawPowerOfAttorney).filter(LawPowerOfAttorney.id == poa.id).delete()
        if client is not None and client.id:
            db.query(LawClients).filter(LawClients.id == client.id).delete()
        if user is not None and user.id:
            db.query(AccessProfiles).filter(AccessProfiles.id == user.id).delete()
        if own_case is not None and own_case.id:
            db.query(LawCases).filter(LawCases.id == own_case.id).delete()
        if other_case is not None and other_case.id:
            db.query(LawCases).filter(LawCases.id == other_case.id).delete()
        db.commit()
        db.close()


def test_conflict_check_matches_encrypted_national_id():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:12]
    client = None
    national_id = f"CI{suffix}"
    try:
        case = db.query(LawCases).filter(LawCases.office_id == 1).first()
        client = LawClients(
            office_id=1,
            case_id=case.id if case else None,
            name=f"موكل فحص تعارض {suffix}",
            national_id=national_id,
            is_deleted=0,
        )
        db.add(client)
        db.commit()
        client_id = client.id

        result = perform_conflict_check(
            db=db,
            office_id=1,
            id_number=national_id,
        )

        assert any(match["client_id"] == client_id for match in result["client_matches"])
    finally:
        if client is not None and client.id:
            db.query(LawClients).filter(LawClients.id == client.id).delete()
            db.commit()
        db.close()
