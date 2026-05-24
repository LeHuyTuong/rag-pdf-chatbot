from app.config import Settings
from app.graph.neo4j_client import Neo4jClient


class FakeSession:
    def __init__(self, queries):
        self.queries = queries

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def run(self, query, params):
        self.queries.append((query, params))
        return [{'connected': 1}]


class FakeDriver:
    def __init__(self):
        self.verified = False
        self.closed = False
        self.queries = []

    def verify_connectivity(self):
        self.verified = True

    def session(self, database=None):
        assert database == 'neo4j'
        return FakeSession(self.queries)

    def close(self):
        self.closed = True


def test_neo4j_client_accepts_mock_driver_without_remote_connection():
    driver = FakeDriver()
    settings = Settings(_env_file=None, NEO4J_DATABASE='neo4j')
    client = Neo4jClient(settings, driver=driver)

    client.verify_connectivity()
    client.close()

    assert driver.verified is True
    assert driver.closed is True
    assert 'RETURN 1 AS connected' in driver.queries[0][0]
