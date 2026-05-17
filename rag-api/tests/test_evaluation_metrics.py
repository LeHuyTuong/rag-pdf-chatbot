from pathlib import Path
from app.services.evaluation_service import EvaluationService


def test_evaluation_uses_consistent_denominators(tmp_path: Path):
    items = [
        {"id":"a1","question":"Ai?","expected_keywords":["Ngô Quyền"],"required_source_keywords":["938"],"should_refuse":False,"category":"answerable"},
        {"id":"r1","question":"Blockchain?","expected_keywords":[],"required_source_keywords":[],"should_refuse":True,"category":"refusal"},
    ]
    responses = [
        {"answer":"Bạch Đằng 938 do Ngô Quyền lãnh đạo.","confidence":0.9,"sources":[{"chunk_id":"c1","text":"938 Ngô Quyền"}],"used_context":"Bạch Đằng 938 do Ngô Quyền lãnh đạo."},
        {"answer":"Tài liệu hiện có chưa đủ để trả lời chắc chắn.","confidence":0.25,"sources":[]},
    ]
    report = EvaluationService().evaluate_items(items, responses, tmp_path)
    assert report["answerable_total"] == 1
    assert report["refusal_total"] == 1
    assert report["overall_pass_rate"] == 1.0
    assert report["answer_accuracy"] == 1.0
    assert report["refusal_accuracy"] == 1.0
