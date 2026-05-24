import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.graph.neo4j_client import Neo4jClient


def main() -> None:
    settings = get_settings()
    with Neo4jClient(settings) as client:
        client.verify_connectivity()
        schema = client.create_constraints()
    print(f'neo4j_connection=ok database={settings.neo4j_database}')
    print(f'graph_constraints_created_or_present={len(schema["constraints"])}')
    for constraint in schema['constraints']:
        print(f'constraint={constraint}')
    print(f'graph_indexes_created_or_present={len(schema["indexes"])}')
    for index in schema['indexes']:
        print(f'index={index}')


if __name__ == '__main__':
    main()
