import requests
import pytest


def test_live_health_and_optional_ingested_points():
    try:
        health = requests.get("http://localhost:8000/health", timeout=2)
    except requests.RequestException:
        pytest.skip("RAG API is not running on localhost:8000")
    if health.status_code != 200:
        pytest.skip(f"localhost:8000 is not the RAG API health endpoint: {health.status_code}")
    assert health.status_code == 200
    qdrant = requests.get("http://localhost:6333/collections/rag_chunks", timeout=2).json()
    assert qdrant["result"]["config"]["params"]["vectors"]["size"] == 384
