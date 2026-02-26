"""Integration tests for Browse REST API using the real SQLite DB."""
import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.repository.mitre_repository import MITRERepository


@pytest.fixture(scope="module")
def client():
    """Use TestClient against the live app with the real mitre.db."""
    # We test against the actual app (with real DB) for integration coverage.
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestHealthEndpoint:
    def test_health_ok(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestTacticsEndpoint:
    def test_list_tactics_returns_14(self, client):
        resp = client.get("/api/v1/tactics")
        assert resp.status_code == 200
        tactics = resp.json()
        assert len(tactics) == 14

    def test_tactic_schema(self, client):
        resp = client.get("/api/v1/tactics")
        first = resp.json()[0]
        assert "attack_id" in first
        assert "name" in first
        assert "shortname" in first


class TestTechniquesByTacticEndpoint:
    def test_returns_techniques(self, client):
        tactics = client.get("/api/v1/tactics").json()
        tac_id = tactics[0]["id"]
        resp = client.get(f"/api/v1/tactics/{tac_id}/techniques")
        assert resp.status_code == 200
        assert len(resp.json()) > 0

    def test_404_for_unknown_tactic(self, client):
        resp = client.get("/api/v1/tactics/999999/techniques")
        assert resp.status_code == 404


class TestTechniqueDetailEndpoint:
    def test_get_t1078(self, client):
        resp = client.get("/api/v1/techniques/T1078")
        assert resp.status_code == 200
        data = resp.json()
        assert data["attack_id"] == "T1078"
        assert "mitigations" in data
        assert "tactic_names" in data
        assert len(data["mitigations"]) > 0

    def test_subtechnique_has_parent(self, client):
        # Find a subtechnique in real DB
        with SessionLocal() as db:
            repo = MITRERepository(db)
            results = repo.search_techniques("T1078.001")
            if not results:
                pytest.skip("No subtechniques found matching T1078.001")
        resp = client.get("/api/v1/techniques/T1078.001")
        if resp.status_code == 404:
            pytest.skip("T1078.001 not in DB")
        data = resp.json()
        assert data["is_subtechnique"] is True
        assert data["parent_attack_id"] == "T1078"

    def test_404_for_unknown(self, client):
        resp = client.get("/api/v1/techniques/T9999")
        assert resp.status_code == 404


class TestSearchEndpoint:
    def test_search_returns_results(self, client):
        resp = client.get("/api/v1/techniques/search?q=phishing")
        assert resp.status_code == 200
        assert len(resp.json()) > 0

    def test_search_too_short(self, client):
        resp = client.get("/api/v1/techniques/search?q=a")
        assert resp.status_code == 422

    def test_search_no_match(self, client):
        resp = client.get("/api/v1/techniques/search?q=xyzzy_impossible")
        assert resp.status_code == 200
        assert resp.json() == []


class TestMitigationEndpoint:
    def test_get_known_mitigation(self, client):
        with SessionLocal() as db:
            repo = MITRERepository(db)
            mits = repo.get_mitigations_for_technique("T1078")
            if not mits:
                pytest.skip("No mitigations for T1078")
            attack_id = mits[0]["mitigation"].attack_id
        resp = client.get(f"/api/v1/mitigations/{attack_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["attack_id"] == attack_id

    def test_404_unknown(self, client):
        resp = client.get("/api/v1/mitigations/M9999")
        assert resp.status_code == 404


class TestSyncStatusEndpoint:
    def test_sync_status_returns_data(self, client):
        resp = client.get("/api/v1/sync/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "techniques_count" in data
