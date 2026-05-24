import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.graph.neo4j_client import Neo4jClient


def main() -> int:
    settings = get_settings()
    if not settings.neo4j_uri or not settings.neo4j_auth:
        print('Neo4j AuraDB connection FAIL: required connection settings are missing')
        return 1

    try:
        with Neo4jClient(settings) as client:
            client.verify_connectivity()
    except Exception as error:
        print(f'Neo4j AuraDB connection FAIL: {error.__class__.__name__}')
        return 1

    print('Neo4j AuraDB connection PASS')
    print(f'URI scheme: {urlparse(settings.neo4j_uri).scheme or "hidden"}')
    print(f'database: {settings.neo4j_database}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
