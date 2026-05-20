from app.services.query_rewriter import rewrite_queries


def test_rewrite_reason_question_for_doi_moi():
    question = 'Vì sao Việt Nam phải tiến hành công cuộc Đổi mới từ năm 1986?'

    queries = rewrite_queries(question)

    assert queries[0] == question
    assert any('nguyên nhân Việt Nam tiến hành Đổi mới năm 1986' in query for query in queries)
    assert any('khủng hoảng kinh tế xã hội trước Đại hội VI' in query for query in queries)
    assert any('nhìn thẳng vào sự thật' in query for query in queries)
    assert len(queries) == len(set(queries))


def test_rewrite_handles_unaccented_analytic_question():
    queries = rewrite_queries('Tai sao Viet Nam phai Doi moi nam 1986?')

    assert any('cơ chế quản lý kinh tế cũ' in query for query in queries)
    assert any('kế hoạch 5 năm 1976 1980' in query for query in queries)
