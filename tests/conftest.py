"""Deterministic, synthetic database fixtures for the CI test database."""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from create_superadmin import hash_pin
from database.database import SessionLocal, init_db
from database.models import AccessProfiles, LawCases, LawClients, LawOffices


@pytest.fixture(scope="session", autouse=True)
def seed_ci_database():
    """Provide isolated synthetic records assumed by legacy integration tests."""
    init_db()
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        end = (now + timedelta(days=3650)).strftime("%Y-%m-%d %H:%M:%S")
        for office_id in (1, 6):
            office = db.query(LawOffices).filter(LawOffices.id == office_id).first()
            if office is None:
                office = LawOffices(
                    id=office_id,
                    name=f"CI Test Office {office_id}",
                    status_key="active",
                    subscription_plan="yearly",
                    subscription_end=end,
                    is_active=1,
                    is_deleted=0,
                )
                db.add(office)
            else:
                office.is_active = 1
                office.subscription_plan = "yearly"
                office.subscription_end = end
        db.flush()

        user = db.query(AccessProfiles).filter(
            AccessProfiles.username == "R1990"
        ).first()
        if user is None:
            user = AccessProfiles(
                name="CI Synthetic Test User",
                username="R1990",
                phone="+966500000001",
                email="r1990@example.test",
                role="مدير المكتب",
                office_id=1,
                access_pin_hash=hash_pin("admin123456"),
                is_active=1,
                is_deleted=0,
                can_view_all_cases=1,
                state="active",
            )
            db.add(user)
            db.flush()
        else:
            user.is_active = 1
            user.is_deleted = 0
            user.office_id = 1
            user.role = "مدير المكتب"
            user.access_pin_hash = hash_pin("admin123456")

        office = db.query(LawOffices).filter(LawOffices.id == 1).first()
        office.owner_user_id = user.id
        db.flush()

        other_user = db.query(AccessProfiles).filter(
            AccessProfiles.username == "CI-OTHER-USER"
        ).first()
        if other_user is None:
            other_user = AccessProfiles(
                name="CI Synthetic User in Another Office",
                username="CI-OTHER-USER",
                phone="+966500000006",
                email="ci-other@example.test",
                role="محامي",
                office_id=6,
                is_active=1,
                is_deleted=0,
                can_view_all_cases=1,
                state="active",
            )
            db.add(other_user)
        else:
            other_user.is_active = 1
            other_user.is_deleted = 0
            other_user.office_id = 6
        other_user.access_pin_hash = hash_pin("admin123456")

        case = db.query(LawCases).filter(
            LawCases.office_id == 1,
            LawCases.case_number == "CI-CASE-001",
        ).first()
        if case is None:
            case = LawCases(
                office_id=1,
                case_number="CI-CASE-001",
                title="قضية اختبار اصطناعية",
                status_key="active",
                is_active=1,
                is_deleted=0,
                created_by_user_id=user.id,
            )
            db.add(case)
            db.flush()

        client = db.query(LawClients).filter(
            LawClients.office_id == 1,
            LawClients.phone == "+966500000002",
        ).first()
        if client is None:
            client = LawClients(
                office_id=1,
                user_id=user.id,
                case_id=case.id,
                name="موكل اختبار اصطناعي",
                phone="+966500000002",
                email="ci-client@example.test",
                is_deleted=0,
            )
            db.add(client)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
