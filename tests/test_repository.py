"""Unit tests for MITRERepository using in-memory SQLite."""
import pytest
from app.repository.mitre_repository import MITRERepository


@pytest.fixture
def repo(db_session, seed_data):
    return MITRERepository(db_session)


class TestGetAllTactics:
    def test_returns_all_tactics(self, repo, seed_data):
        tactics = repo.get_all_tactics()
        assert len(tactics) >= 2

    def test_ordered_by_attack_id(self, repo):
        tactics = repo.get_all_tactics()
        ids = [t.attack_id for t in tactics]
        assert ids == sorted(ids)


class TestSearchTechniques:
    def test_finds_by_name(self, repo):
        results = repo.search_techniques("Valid Accounts")
        assert any(t.attack_id == "T1078" for t in results)

    def test_finds_by_description(self, repo):
        results = repo.search_techniques("credentials")
        assert len(results) >= 1

    def test_multiple_keywords(self, repo):
        results = repo.search_techniques("Valid Accounts, credentials")
        assert any(t.attack_id == "T1078" for t in results)

    def test_empty_keywords_returns_empty(self, repo):
        assert repo.search_techniques("") == []

    def test_no_match_returns_empty(self, repo):
        results = repo.search_techniques("xyzzy_nonexistent_12345")
        assert results == []


class TestGetTechniqueByAttackId:
    def test_found(self, repo):
        tech = repo.get_technique_by_attack_id("T1078")
        assert tech is not None
        assert tech.name == "Valid Accounts"

    def test_not_found(self, repo):
        assert repo.get_technique_by_attack_id("T9999") is None


class TestGetMitigationsForTechnique:
    def test_returns_mitigations(self, repo):
        rows = repo.get_mitigations_for_technique("T1078")
        assert len(rows) >= 1
        assert rows[0]["mitigation"].attack_id == "M1036"

    def test_relationship_description_present(self, repo):
        rows = repo.get_mitigations_for_technique("T1078")
        assert rows[0]["relationship_description"] is not None

    def test_unknown_technique(self, repo):
        assert repo.get_mitigations_for_technique("T9999") == []


class TestGetTechniquesByTactic:
    def test_returns_techniques(self, repo, seed_data):
        tac_id = seed_data["tac1"].id
        techs = repo.get_techniques_by_tactic(tac_id)
        assert any(t.attack_id == "T1078" for t in techs)

    def test_empty_tactic(self, repo, seed_data):
        tac_id = seed_data["tac2"].id
        techs = repo.get_techniques_by_tactic(tac_id)
        assert techs == []


class TestGetSyncLog:
    def test_no_log_returns_none(self, repo):
        log = repo.get_latest_sync_log("mobile-attack")
        assert log is None
