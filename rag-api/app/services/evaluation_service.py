import json
from datetime import datetime, timezone
from pathlib import Path

REFUSAL_TEXT = 'Tài liệu hiện có chưa đủ để trả lời chắc chắn.'


class EvaluationService:
    def evaluate_items(self, items: list[dict], responses: list[dict], report_dir: Path) -> dict:
        details = []
        answerable_total = sum(1 for item in items if not item.get('should_refuse', False))
        refusal_total = sum(1 for item in items if item.get('should_refuse', False))
        correct_answers = retrieval_hits = valid_citations = answers_with_citation = faithful_answers = correct_refusals = 0
        for item, response in zip(items, responses):
            normalized = self._normalize_response(response)
            answer = normalized['answer']
            sources = normalized['sources']
            retrieved_chunks = normalized.get('retrieved_chunks', [s.get('chunk_id') for s in sources])
            used_text = normalized.get('used_context', '')
            source_blob = ' '.join(json.dumps(s, ensure_ascii=False) for s in sources) + ' ' + used_text
            should_refuse = item.get('should_refuse', False)
            expected = item.get('expected_keywords', [])
            required = item.get('required_source_keywords', [])
            if should_refuse:
                refused = REFUSAL_TEXT.lower() in answer.lower() and normalized['confidence'] <= 0.35
                correct_refusals += int(refused)
                checks = {'refusal_ok': refused}
                passed = refused
            else:
                answer_ok = self._contains_all(answer, expected)
                retrieval_ok = self._contains_all(answer + ' ' + source_blob, required) if required else bool(sources)
                has_citation = bool(sources)
                citation_ok = has_citation and (self._contains_any(answer + ' ' + source_blob, expected) or self._contains_all(answer + ' ' + source_blob, required))
                faithful_ok = answer_ok and has_citation and self._answer_supported(answer, answer + ' ' + source_blob, expected)
                correct_answers += int(answer_ok)
                retrieval_hits += int(retrieval_ok)
                answers_with_citation += int(has_citation)
                valid_citations += int(citation_ok)
                faithful_answers += int(faithful_ok)
                checks = {'answer_ok': answer_ok, 'retrieval_ok': retrieval_ok, 'citation_ok': citation_ok, 'faithful_ok': faithful_ok}
                passed = answer_ok and retrieval_ok and citation_ok and faithful_ok
            details.append({
                'question_id': item.get('id'), 'category': item.get('category'), 'question': item.get('question'),
                'expected_keywords': expected, 'required_source_keywords': required, 'should_refuse': should_refuse,
                'actual_answer': answer, 'confidence': normalized['confidence'], 'retrieved_chunks': retrieved_chunks,
                'sources': sources, 'checks': checks, 'passed': passed,
                'reason': 'Passed only if all applicable category checks are true; metrics use category-specific denominators.',
            })
        total = len(items)
        passed_count = sum(1 for d in details if d['passed'])
        report = {
            'total_questions': total,
            'answerable_total': answerable_total,
            'refusal_total': refusal_total,
            'passed': passed_count,
            'failed': total - passed_count,
            'overall_pass_rate': self._ratio(passed_count, total),
            'answer_accuracy': self._ratio(correct_answers, answerable_total),
            'retrieval_hit_rate': self._ratio(retrieval_hits, answerable_total),
            'citation_accuracy': self._ratio(valid_citations, answers_with_citation),
            'faithfulness_score': self._ratio(faithful_answers, answerable_total),
            'refusal_accuracy': self._ratio(correct_refusals, refusal_total),
            'formulas': {
                'overall_pass_rate': 'passed / total_questions',
                'answer_accuracy': 'correct_answerable_answers / answerable_total',
                'retrieval_hit_rate': 'answerable_questions_with_required_source_in_top_k / answerable_total',
                'citation_accuracy': 'answers_with_valid_citation / answers_with_citation',
                'faithfulness_score': 'answerable_answers_supported_by_context / answerable_total',
                'refusal_accuracy': 'correct_refusals / refusal_total',
            },
            'details': details,
        }
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f'evaluation_report_{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}.json'
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        report['report_path'] = str(path)
        return report

    def _normalize_response(self, response: dict) -> dict:
        payload = response.get('answer', response) if isinstance(response.get('answer'), dict) else response
        return {
            'answer': payload.get('answer', ''),
            'confidence': float(payload.get('confidence', 0) or 0),
            'sources': payload.get('sources', []) or [],
            'retrieved_chunks': payload.get('retrieved_chunks', []),
            'used_context': payload.get('used_context', ''),
        }

    def _contains_all(self, text: str, keywords: list[str]) -> bool:
        return all(keyword.lower() in text.lower() for keyword in keywords)

    def _contains_any(self, text: str, keywords: list[str]) -> bool:
        return any(keyword.lower() in text.lower() for keyword in keywords)

    def _answer_supported(self, answer: str, context: str, expected: list[str]) -> bool:
        if not self._contains_all(answer, expected):
            return False
        proper_numbers = [token for token in answer.replace('\n', ' ').split() if any(ch.isdigit() for ch in token)]
        return all(token.strip('.,;:') in context for token in proper_numbers)

    def _ratio(self, numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 4) if denominator else 1.0
