from scripts import batch_eval_history_rag as eval_script


def _trap_question():
    return next(question for question in eval_script.QUESTIONS if question.question_id == 'E01')


def _record(answer: str):
    return eval_script.make_record(
        _trap_question(),
        {
            'answer': answer,
            'sources': [],
        },
        latency_ms=123,
    )


def _quick_question():
    return next(question for question in eval_script.QUESTIONS if question.question_id == 'Q06')


def test_trap_weak_refusal_is_not_hallucination_risk():
    record = _record('Dựa trên các tài liệu được cung cấp, không có thông tin nào đề cập đến Đinh Bộ Lĩnh là ai.')

    assert record['checks']['weak_refusal'] is True
    assert record['checks']['controlled_refusal'] is False
    assert record['checks']['hallucination_risk'] is False
    assert record['verdict'] == 'WARNING_REFUSAL_WEAK'


def test_trap_refusal_with_question_detail_is_not_hallucination_risk():
    record = _record(
        'Thông tin về việc Đinh Bộ Lĩnh dẹp loạn 12 sứ quân không có trong các tài liệu được cung cấp. '
        'Các tài liệu này chỉ tập trung vào giai đoạn lịch sử Việt Nam từ năm 1986 đến năm 2000.'
    )

    assert record['checks']['controlled_refusal'] is True
    assert record['checks']['true_hallucination'] is False
    assert record['checks']['hallucination_risk'] is False
    assert record['verdict'] == 'PASS_TRAP_REFUSAL'


def test_trap_controlled_refusal_passes():
    record = _record(
        'Tài liệu hiện tại không chứa thông tin về Đinh Bộ Lĩnh vì nội dung tài liệu đang viết về '
        'giai đoạn 1986–2000. Cần bổ sung tài liệu về lịch sử Việt Nam thế kỷ X hoặc thời Đinh '
        'để trả lời chính xác.'
    )

    assert record['checks']['controlled_refusal'] is True
    assert record['checks']['hallucination_risk'] is False
    assert record['verdict'] == 'PASS_TRAP_REFUSAL'


def test_trap_true_hallucination_fails():
    record = _record('Đinh Bộ Lĩnh là người dẹp loạn 12 sứ quân, lập nước Đại Cồ Việt tại Hoa Lư.')

    assert record['checks']['true_hallucination'] is True
    assert record['checks']['hallucination_risk'] is True
    assert record['verdict'] == 'FAIL_HALLUCINATION_RISK'


def test_related_chunks_are_normalized_when_sources_empty():
    record = eval_script.make_record(
        _quick_question(),
        {
            'answer': 'Không có thông tin đầy đủ, nhưng tài liệu liên quan có trong các đoạn truy xuất.',
            'sources': [],
            'related_chunks': [
                {
                    'chunk_id': 'chunk-1',
                    'file_name': 'history.pdf',
                    'page_start': 196,
                    'page_end': 196,
                    'chunk_index': 192,
                    'score': 0.94,
                }
            ],
        },
        latency_ms=123,
    )

    assert len(record['sources']) == 1
    assert record['sources'][0]['fileName'] == 'history.pdf'
    assert record['sources'][0]['pageNumber'] == 196
    assert record['sources'][0]['chunkIndex'] == 192
    assert record['checks']['has_sources'] is True
    assert record['checks']['source_mapping_issue'] is True


def test_answer_source_text_without_raw_sources_marks_mapping_issue():
    record = eval_script.make_record(
        _quick_question(),
        {
            'answer': 'Câu trả lời có trích dẫn. Nguồn: fileName=history.pdf, pageNumber=1, chunkIndex=2.',
            'sources': [],
        },
        latency_ms=123,
    )

    assert record['checks']['has_sources'] is False
    assert record['checks']['source_mapping_issue'] is True
    assert 'source-like data' in ' '.join(record['notes'])
