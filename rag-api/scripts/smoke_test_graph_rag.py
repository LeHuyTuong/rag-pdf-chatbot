import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.graph.graph_retriever import GraphRetriever
from app.graph.neo4j_client import Neo4jClient


QUESTIONS = [
    'Đại hội VI liên quan đến công cuộc Đổi mới như thế nào?',
    'Cơ chế bao cấp liên quan gì đến lạm phát?',
    'Kinh tế nhiều thành phần có quan hệ gì với giải phóng lực lượng sản xuất?',
    'Việt Nam có thay đổi đối ngoại nào sau Đổi mới?',
    'Đinh Bộ Lĩnh là ai?',
]


def main() -> int:
    parser = argparse.ArgumentParser(description='Direct smoke test for Phase 1 graph retrieval.')
    parser.add_argument('--document-id', default=None, help='Optional graph document scope.')
    parser.add_argument('--top-k', type=int, default=10)
    args = parser.parse_args()

    with Neo4jClient(get_settings()) as client:
        client.verify_connectivity()
        retriever = GraphRetriever(client)
        for position, question in enumerate(QUESTIONS, start=1):
            evidence = retriever.retrieve(question, document_id=args.document_id, top_k=args.top_k)
            print(f'[Q{position}] {question}')
            print(f'Graph evidence count: {len(evidence)}')
            if not evidence:
                print('No graph evidence found')
                continue
            for item in evidence:
                print(f'- {item.source_entity} --{item.relation_type}--> {item.target_entity}')
                print(f'  description={item.description}')
                print(f'  source={item.file_name} page={item.page_number} chunk={item.chunk_index}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
