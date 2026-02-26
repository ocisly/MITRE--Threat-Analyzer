"""Shared pytest fixtures — in-memory SQLite for fast, isolated tests."""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.models.base import Base
from app.models import tactic, technique, mitigation, sync_log, associations  # ensure all models are loaded
from app.database import SessionLocal


# ── In-memory SQLite engine ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # Enable WAL mode for in-memory DB (consistency with prod config)
    @event.listens_for(eng, "connect")
    def set_pragma(conn, _):
        conn.execute("PRAGMA journal_mode=WAL")

    Base.metadata.create_all(eng)
    return eng


@pytest.fixture(scope="session")
def db_session(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        yield session


@pytest.fixture(scope="session")
def seed_data(db_session):
    """Insert minimal test data into in-memory DB."""
    from app.models.tactic import Tactic
    from app.models.technique import Technique
    from app.models.mitigation import Mitigation
    from app.models.associations import technique_tactic, technique_mitigation
    import json

    tac1 = Tactic(
        stix_id="x-mitre-tactic--ta0001",
        attack_id="TA0001",
        name="Initial Access",
        shortname="initial-access",
        description="The adversary is trying to get into your network.",
        url="https://attack.mitre.org/tactics/TA0001/",
        domain="enterprise-attack",
    )
    tac2 = Tactic(
        stix_id="x-mitre-tactic--ta0004",
        attack_id="TA0004",
        name="Privilege Escalation",
        shortname="privilege-escalation",
        description="The adversary is trying to gain higher-level permissions.",
        url="https://attack.mitre.org/tactics/TA0004/",
        domain="enterprise-attack",
    )

    tech1 = Technique(
        stix_id="attack-pattern--t1078",
        attack_id="T1078",
        name="Valid Accounts",
        description="Adversaries may obtain and abuse credentials of existing accounts.",
        detection="Monitor for unusual account activity.",
        is_subtechnique=False,
        platforms=json.dumps(["Windows", "Linux", "macOS"]),
        data_sources=json.dumps(["Authentication logs"]),
        url="https://attack.mitre.org/techniques/T1078/",
        domain="enterprise-attack",
    )

    mit1 = Mitigation(
        stix_id="course-of-action--m1036",
        attack_id="M1036",
        name="Account Use Policies",
        description="Configure features related to account use like login attempt lockouts.",
        url="https://attack.mitre.org/mitigations/M1036/",
        domain="enterprise-attack",
    )

    db_session.add_all([tac1, tac2, tech1, mit1])
    db_session.flush()

    # Link technique <-> tactic
    db_session.execute(
        technique_tactic.insert().values(technique_id=tech1.id, tactic_id=tac1.id)
    )
    # Link technique <-> mitigation
    db_session.execute(
        technique_mitigation.insert().values(
            technique_id=tech1.id,
            mitigation_id=mit1.id,
            relationship_description="Use account policies to prevent credential abuse.",
        )
    )
    db_session.commit()

    return {"tac1": tac1, "tac2": tac2, "tech1": tech1, "mit1": mit1}


@pytest.fixture(scope="function")
def test_client(engine, monkeypatch):
    """FastAPI TestClient with the in-memory DB injected."""
    from app import main as main_module
    from app import database as db_module

    # Patch SessionLocal to use the in-memory engine
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    class PatchedSessionLocal:
        def __enter__(self):
            self._session = TestSession()
            return self._session

        def __exit__(self, *args):
            self._session.close()

    monkeypatch.setattr(db_module, "SessionLocal", PatchedSessionLocal)

    # Disable lifespan for simple HTTP tests
    from fastapi.testclient import TestClient as TC
    with TC(main_module.app, raise_server_exceptions=True) as client:
        yield client
