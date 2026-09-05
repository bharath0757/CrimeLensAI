"""Tests for GraphRepository and Neo4jConnectionManager with mocked Neo4j driver."""

from unittest.mock import MagicMock

import pytest
from app.repositories.graph_repository import GraphRepository


class TestGraphRepository:
    @pytest.fixture
    def repo(self):
        driver = MagicMock()
        return GraphRepository(driver), driver

    def test_entity_exists_returns_true(self, repo):
        repository, driver = repo
        session_mock = MagicMock()
        session_mock.execute_read.return_value = True
        driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        assert repository.entity_exists("test-id") is True
        session_mock.execute_read.assert_called_once()

    def test_entity_exists_returns_false(self, repo):
        repository, driver = repo
        session_mock = MagicMock()
        session_mock.execute_read.return_value = False
        driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        assert repository.entity_exists("nonexistent") is False

    def test_upsert_uses_merge(self, repo):
        repository, driver = repo
        session_mock = MagicMock()
        session_mock.execute_write.return_value = {"existed": False, "case_ids": ["CASE-001"]}
        driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        result = repository.upsert_entity(
            entity_id="test-id", entity_type="PERSON",
            value="Test", canonical_value="test",
            confidence=0.9, case_id="CASE-001",
            source_field="fir_text", start_offset=0, end_offset=10,
        )
        assert result == {"existed": False, "case_ids": ["CASE-001"]}
        session_mock.execute_write.assert_called_once()

    def test_upsert_existed_logic(self, repo):
        repository, driver = repo
        session_mock = MagicMock()
        
        # We need to simulate the tx.run calls inside _do_upsert
        def fake_execute_write(func):
            tx = MagicMock()
            
            # The first tx.run is the MERGE which returns `existed`
            merge_result = MagicMock()
            merge_result.single.return_value = {"existed": True, "e": {}, "c": {}}
            
            # The second tx.run is the MATCH which returns cases
            cases_result = [{"case_id": "CASE-123"}]
            
            tx.run.side_effect = [merge_result, cases_result]
            
            return func(tx)

        session_mock.execute_write.side_effect = fake_execute_write
        driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        res = repository.upsert_entity(
            entity_id='1', entity_type='PHONE', value='123', canonical_value='123',
            confidence=1.0, case_id='CASE-123', source_field='f', start_offset=0, end_offset=1
        )
        assert res['existed'] is True
        assert res['case_ids'] == ["CASE-123"]

    def test_create_relationship_calls_execute_write(self, repo):
        repository, driver = repo
        session_mock = MagicMock()
        session_mock.execute_write.return_value = None
        driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        repository.create_relationship(
            source_entity_id="a", target_entity_id="b",
            relationship_type="USES", source_case_id="CASE-001",
            confidence=0.9, why_linked="Test evidence.",
            relationship_id="rel-1",
        )
        session_mock.execute_write.assert_called_once()

    def test_get_cross_case_linkage_calls_execute_read(self, repo):
        repository, driver = repo
        session_mock = MagicMock()
        session_mock.execute_read.return_value = [
            {"case_id": "CASE-002", "shared_entities": [{"entity_id": "e1", "entity_type": "PHONE"}]}
        ]
        driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        result = repository.get_cross_case_linkage("CASE-001")
        assert isinstance(result, list)
        session_mock.execute_read.assert_called_once()

    def test_get_shortest_path_calls_execute_read(self, repo):
        repository, driver = repo
        session_mock = MagicMock()
        session_mock.execute_read.return_value = None
        driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        result = repository.get_shortest_path("a", "b")
        assert result is None
        session_mock.execute_read.assert_called_once()

class TestNeo4jConnectionManager:
    def test_verify_connectivity_returns_true_when_connected(self):
        from app.core.neo4j import Neo4jConnectionManager
        manager = Neo4jConnectionManager()
        manager._driver = MagicMock()
        manager._driver.verify_connectivity.return_value = None
        assert manager.verify_connectivity() is True

    def test_verify_connectivity_returns_false_when_disconnected(self):
        from app.core.neo4j import Neo4jConnectionManager
        manager = Neo4jConnectionManager()
        manager._driver = MagicMock()
        manager._driver.verify_connectivity.side_effect = Exception("Connection refused")
        assert manager.verify_connectivity() is False

    def test_driver_property_raises_when_not_initialized(self):
        from app.core.neo4j import Neo4jConnectionManager
        manager = Neo4jConnectionManager()
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = manager.driver

    def test_close_sets_driver_to_none(self):
        from app.core.neo4j import Neo4jConnectionManager
        manager = Neo4jConnectionManager()
        manager._driver = MagicMock()
        manager.close()
        assert manager._driver is None

    def test_execute_query_uses_parameterized_cypher(self):
        from app.core.neo4j import Neo4jConnectionManager
        manager = Neo4jConnectionManager()
        mock_driver = MagicMock()
        manager._driver = mock_driver
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = []

        manager.execute_query("MATCH (n) RETURN n", {"limit": 10})
        mock_session.run.assert_called_once_with("MATCH (n) RETURN n", {"limit": 10})
