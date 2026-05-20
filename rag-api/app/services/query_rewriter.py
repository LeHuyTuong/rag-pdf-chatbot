import re
import unicodedata


ANALYTIC_MARKERS = (
    'vi sao',
    'tai sao',
    'nguyen nhan',
    'y nghia',
    'phan tich',
    'so sanh',
)


def _fold_for_matching(text: str) -> str:
    folded = unicodedata.normalize('NFD', (text or '').lower())
    folded = ''.join(ch for ch in folded if unicodedata.category(ch) != 'Mn')
    folded = folded.replace('đ', 'd')
    folded = folded.replace('Đ', 'd')
    return re.sub(r'\s+', ' ', folded).strip()


def _append_unique(items: list[str], value: str) -> None:
    value = re.sub(r'\s+', ' ', value or '').strip()
    if value and value not in items:
        items.append(value)


def rewrite_queries(question: str) -> list[str]:
    question = (question or '').strip()
    if not question:
        return []

    folded = _fold_for_matching(question)
    queries = [question]
    is_analytic = any(marker in folded for marker in ANALYTIC_MARKERS)
    is_doi_moi = ('doi moi' in folded or 'dai hoi vi' in folded or '1986' in folded) and 'viet nam' in folded

    if is_analytic:
        reason_query = re.sub(r'(?i)\b(vì sao|tại sao)\b', 'nguyên nhân', question)
        _append_unique(queries, reason_query)
        _append_unique(queries, f'nguyên nhân {question}')
        _append_unique(queries, f'bối cảnh nguyên nhân dẫn đến {question}')

    if is_doi_moi:
        for query in [
            'nguyên nhân Việt Nam tiến hành Đổi mới năm 1986',
            'bối cảnh khủng hoảng kinh tế xã hội trước Đại hội VI',
            'Đại hội VI nhìn thẳng vào sự thật nói rõ sự thật',
            'sai lầm khuyết điểm trước Đại hội VI kế hoạch 5 năm 1976 1980',
            'cơ chế quản lý kinh tế cũ lạc hậu quan liêu bao cấp',
            'nóng vội công nghiệp hóa chỉ tiêu kế hoạch quá cao công nghiệp nặng',
            'bất hợp lý cơ cấu kinh tế cải tạo xã hội chủ nghĩa thành phần kinh tế',
        ]:
            _append_unique(queries, query)

    if 'so sanh' in folded and is_doi_moi:
        _append_unique(queries, 'tình hình Việt Nam trước Đổi mới sau Đổi mới')
        _append_unique(queries, 'khủng hoảng trước Đổi mới thành tựu sau Đổi mới')

    return queries[:10]
