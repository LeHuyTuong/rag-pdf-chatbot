from app.graph.graph_retriever import GraphRetriever


class EmptyNeo4jClient:
    def __init__(self):
        self.params = []

    def run_query(self, _query, params=None):
        self.params.append(params)
        return [{'total': 0}]


def test_graph_retriever_returns_empty_when_no_entity_matches():
    client = EmptyNeo4jClient()
    retriever = GraphRetriever(client)

    evidence = retriever.retrieve('Đinh Bộ Lĩnh là ai?', document_id='document-1')

    assert evidence == []
    assert client.params
    assert client.params == [{'document_id': 'document-1', 'document_property': 'documentId'}]
