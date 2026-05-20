import argparse
import csv
import json
import multiprocessing as mp
import os
import re
import sys
import time
import unicodedata
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import pymysql
import requests
from dotenv import load_dotenv


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


ROOT_DIR = Path(__file__).resolve().parents[2]
RAG_API_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = RAG_API_DIR / 'storage' / 'eval'

SESSION_ID = 'batch-eval-history-rag'
MISSING_DOCUMENT_MESSAGE = (
    'Cannot run batch evaluation: missing documentId. '
    'Set SMOKE_DOCUMENT_ID or ingest/select a document first.'
)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

DIACRITIC_CHARS = set(
    'ăâđêôơư'
    'áàảãạấầẩẫậắằẳẵặ'
    'éèẻẽẹếềểễệ'
    'íìỉĩị'
    'óòỏõọốồổỗộớờởỡợ'
    'úùủũụứừửữự'
    'ýỳỷỹỵ'
)

DIACRITIC_WORDS = (
    'Việt Nam',
    'Đổi mới',
    'Đại hội',
    'kinh tế',
    'chính trị',
    'xã hội',
    'khủng hoảng',
)

OLD_NON_DIACRITIC_PHRASES = (
    'Dua tren',
    'Khong co thong tin',
    'Khong tim thay',
    'Tai lieu nay',
    'cac doan tai lieu',
    'No reliable source found',
)

CONTROLLED_REFUSAL_MARKERS = (
    'tài liệu hiện tại không chứa thông tin',
    'tài liệu hiện tại không chứa đủ thông tin',
    'không có thông tin trong tài liệu',
    'không có thông tin nào đề cập',
    'không có thông tin về',
    'không được đề cập trong tài liệu',
    'các tài liệu này tập trung vào',
    'nội dung tài liệu viết về giai đoạn 1986-2000',
    'nội dung tài liệu viết về giai đoạn 1986–2000',
    'giai đoạn 1986-2000',
    'giai đoạn 1986–2000',
    'cần bổ sung tài liệu khác',
    'cần bổ sung tài liệu',
    'không đủ cơ sở từ nguồn hiện tại',
    'không đủ cơ sở từ tài liệu hiện tại',
    'tài liệu hiện có chưa cung cấp đủ thông tin',
    'tài liệu hiện tại chưa có thông tin',
)

REFUSAL_MARKERS = (
    'không có thông tin',
    'không có đủ thông tin',
    'không có trong tài liệu',
    'không có trong các tài liệu',
    'không có trong nguồn tài liệu',
    'không có trong các nguồn tài liệu',
    'không tìm thấy thông tin',
    'không được đề cập',
    'không đề cập',
    'không đủ cơ sở',
    'không đủ thông tin',
    'chưa cung cấp đủ thông tin',
    'not enough information',
    'insufficient information',
)

REFUSAL_SCOPE_MARKERS = (
    '1986-2000',
    '1986–2000',
    'từ năm 1986 đến năm 2000',
    'giai đoạn từ năm 1986 đến năm 2000',
    'tập trung vào lịch sử việt nam giai đoạn',
    'các tài liệu này tập trung vào',
    'các nguồn tài liệu hiện tại chỉ tập trung',
    'cần bổ sung tài liệu',
)

INSUFFICIENT_INFO_MARKERS = (
    'không đủ thông tin',
    'chưa đủ thông tin',
    'không có thông tin',
    'không tìm thấy',
    'không đủ cơ sở',
    'tài liệu không nêu',
    'tài liệu chưa nêu',
    'thiếu thông tin',
    'insufficient',
    'not enough information',
)

TRUE_HALLUCINATION_MARKERS = (
    'dẹp loạn 12 sứ quân',
    'dẹp loạn mười hai sứ quân',
    'lập nước Đại Cồ Việt',
    'Đại Cồ Việt',
    'Hoa Lư',
    'Đinh Tiên Hoàng',
    'sinh tại',
    'quê ở',
    'Nguyễn Bặc là',
    'Đinh Điền là',
    'Phạm Hạp là',
    'Lê Hoàn là',
    'tướng dưới trướng gồm',
    'dưới trướng gồm',
    'quốc hiệu là',
)


@dataclass(frozen=True)
class EvalQuestion:
    question_id: str
    group: str
    group_name: str
    question: str
    expected_behavior: str
    is_trap: bool


@dataclass(frozen=True)
class AskResult:
    raw_response: dict[str, Any]
    latency_ms: int
    error: str | None = None
    rate_limited: bool = False


EXPECTED_A = (
    'RAG nên trả lời dựa trên tài liệu 1986–2000. Cần có citation/source. '
    'Nếu tài liệu không đủ thông tin chi tiết, phải nói rõ phần thiếu, không bịa.'
)

EXPECTED_B = (
    'RAG nên trả lời được bằng tổng hợp từ tài liệu. Cần citation/source. '
    'Câu “vì sao” phải có giải thích nguyên nhân, không chỉ copy một câu ngắn.'
)

EXPECTED_C = (
    'RAG nên trả lời theo tài liệu 1986–2000. Cần source page/chunk. '
    'Nếu thiếu chi tiết, phải nói thiếu chứ không bịa.'
)

EXPECTED_D = (
    'Đây là nhóm kiểm tra synthesis/reasoning. RAG được phép tổng hợp/suy luận trực tiếp từ context. '
    'Không được dùng kiến thức ngoài tài liệu. Cần source. Nếu context không đủ, phải nêu rõ giới hạn.'
)

EXPECTED_E = (
    'Đây là nhóm bẫy. Nếu hệ thống chỉ có tài liệu 1986–2000, câu trả lời tốt phải từ chối có kiểm soát, '
    'không trả lời chi tiết về Đinh Bộ Lĩnh nếu không có source phù hợp.'
)

EXPECTED_Q = (
    'Q01–Q09 nên trả lời được dựa trên tài liệu 1986–2000. Q10 là câu bẫy; nếu chưa có tài liệu thời Đinh, '
    'phải từ chối có kiểm soát.'
)


QUESTIONS: list[EvalQuestion] = [
    EvalQuestion('A01', 'A', 'Test đúng tài liệu 1986–2000', 'Nguyễn Văn Linh là ai trong bối cảnh công cuộc Đổi mới ở Việt Nam?', EXPECTED_A, False),
    EvalQuestion('A02', 'A', 'Test đúng tài liệu 1986–2000', 'Đỗ Mười là ai và giữ vai trò gì trong giai đoạn 1986–2000?', EXPECTED_A, False),
    EvalQuestion('A03', 'A', 'Test đúng tài liệu 1986–2000', 'Võ Văn Kiệt là ai và có vai trò gì trong thời kỳ Đổi mới?', EXPECTED_A, False),
    EvalQuestion('A04', 'A', 'Test đúng tài liệu 1986–2000', 'Lê Đức Anh là ai trong đời sống chính trị Việt Nam giai đoạn 1986–2000?', EXPECTED_A, False),
    EvalQuestion('A05', 'A', 'Test đúng tài liệu 1986–2000', 'Nông Đức Mạnh xuất hiện trong bối cảnh chính trị nào cuối giai đoạn 1986–2000?', EXPECTED_A, False),
    EvalQuestion('B01', 'B', 'Test sự kiện, thời gian, quan hệ', 'Đại hội VI của Đảng Cộng sản Việt Nam diễn ra khi nào và có ý nghĩa gì?', EXPECTED_B, False),
    EvalQuestion('B02', 'B', 'Test sự kiện, thời gian, quan hệ', 'Đại hội VI đã chỉ ra những sai lầm, khuyết điểm nào trong lãnh đạo kinh tế - xã hội trước Đổi mới?', EXPECTED_B, False),
    EvalQuestion('B03', 'B', 'Test sự kiện, thời gian, quan hệ', 'Vì sao Việt Nam phải tiến hành công cuộc Đổi mới từ năm 1986?', EXPECTED_B, False),
    EvalQuestion('B04', 'B', 'Test sự kiện, thời gian, quan hệ', 'Đường lối Đổi mới tại Đại hội VI tập trung trước hết vào lĩnh vực nào?', EXPECTED_B, False),
    EvalQuestion('B05', 'B', 'Test sự kiện, thời gian, quan hệ', 'Cơ chế quản lý kinh tế trước Đổi mới có những hạn chế gì?', EXPECTED_B, False),
    EvalQuestion('B06', 'B', 'Test sự kiện, thời gian, quan hệ', 'Sau năm 1986, Việt Nam chuyển từ cơ chế kinh tế nào sang cơ chế kinh tế nào?', EXPECTED_B, False),
    EvalQuestion('B07', 'B', 'Test sự kiện, thời gian, quan hệ', 'Chính sách kinh tế nhiều thành phần được hiểu như thế nào trong thời kỳ Đổi mới?', EXPECTED_B, False),
    EvalQuestion('B08', 'B', 'Test sự kiện, thời gian, quan hệ', 'Nông nghiệp Việt Nam thay đổi như thế nào sau khi thực hiện chính sách khoán?', EXPECTED_B, False),
    EvalQuestion('B09', 'B', 'Test sự kiện, thời gian, quan hệ', 'Vì sao Việt Nam từ nước thiếu lương thực trở thành nước xuất khẩu gạo?', EXPECTED_B, False),
    EvalQuestion('B10', 'B', 'Test sự kiện, thời gian, quan hệ', 'Lạm phát ở Việt Nam trong những năm đầu Đổi mới được xử lý như thế nào?', EXPECTED_B, False),
    EvalQuestion('C01', 'C', 'Test quan hệ đối ngoại', 'Việt Nam bình thường hóa quan hệ với Trung Quốc vào năm nào và sự kiện này có ý nghĩa gì?', EXPECTED_C, False),
    EvalQuestion('C02', 'C', 'Test quan hệ đối ngoại', 'Việt Nam bình thường hóa quan hệ với Hoa Kỳ vào năm nào?', EXPECTED_C, False),
    EvalQuestion('C03', 'C', 'Test quan hệ đối ngoại', 'Việt Nam gia nhập ASEAN vào năm nào và vì sao đây là dấu mốc quan trọng?', EXPECTED_C, False),
    EvalQuestion('C04', 'C', 'Test quan hệ đối ngoại', 'Chủ trương đa phương hóa, đa dạng hóa quan hệ đối ngoại được thể hiện như thế nào?', EXPECTED_C, False),
    EvalQuestion('C05', 'C', 'Test quan hệ đối ngoại', 'Đường lối đối ngoại của Việt Nam sau Đổi mới khác gì so với giai đoạn trước?', EXPECTED_C, False),
    EvalQuestion('D01', 'D', 'Câu hỏi khó hơn để test tổng hợp', 'So sánh tình hình kinh tế Việt Nam trước và sau Đổi mới.', EXPECTED_D, False),
    EvalQuestion('D02', 'D', 'Câu hỏi khó hơn để test tổng hợp', 'Phân tích vai trò của Đại hội VI trong việc mở đầu thời kỳ Đổi mới.', EXPECTED_D, False),
    EvalQuestion('D03', 'D', 'Câu hỏi khó hơn để test tổng hợp', 'Những thành tựu lớn nhất của Việt Nam giai đoạn 1986–2000 là gì?', EXPECTED_D, False),
    EvalQuestion('D04', 'D', 'Câu hỏi khó hơn để test tổng hợp', 'Những hạn chế còn tồn tại trong quá trình Đổi mới giai đoạn 1986–2000 là gì?', EXPECTED_D, False),
    EvalQuestion('D05', 'D', 'Câu hỏi khó hơn để test tổng hợp', 'Bài học “lấy dân làm gốc” được thể hiện như thế nào trong đường lối Đổi mới?', EXPECTED_D, False),
    EvalQuestion('D06', 'D', 'Câu hỏi khó hơn để test tổng hợp', 'Vì sao đổi mới kinh tế được đặt làm trọng tâm trước đổi mới chính trị?', EXPECTED_D, False),
    EvalQuestion('D07', 'D', 'Câu hỏi khó hơn để test tổng hợp', 'Việt Nam đã xử lý quan hệ giữa ổn định chính trị và phát triển kinh tế như thế nào trong giai đoạn 1986–2000?', EXPECTED_D, False),
    EvalQuestion('D08', 'D', 'Câu hỏi khó hơn để test tổng hợp', 'Công cuộc Đổi mới đã tác động như thế nào đến đời sống nhân dân?', EXPECTED_D, False),
    EvalQuestion('D09', 'D', 'Câu hỏi khó hơn để test tổng hợp', 'Nền kinh tế hàng hóa nhiều thành phần có ý nghĩa gì đối với việc giải phóng lực lượng sản xuất?', EXPECTED_D, False),
    EvalQuestion('D10', 'D', 'Câu hỏi khó hơn để test tổng hợp', 'Vì sao có thể nói giai đoạn 1986–2000 là thời kỳ chuyển đổi quan trọng của Việt Nam hiện đại?', EXPECTED_D, False),
    EvalQuestion('E01', 'E', 'Câu hỏi bẫy chống hallucination', 'Đinh Bộ Lĩnh là ai?', EXPECTED_E, True),
    EvalQuestion('E02', 'E', 'Câu hỏi bẫy chống hallucination', 'Đinh Bộ Lĩnh sinh ở đâu?', EXPECTED_E, True),
    EvalQuestion('E03', 'E', 'Câu hỏi bẫy chống hallucination', 'Dưới trướng Đinh Bộ Lĩnh có những tướng nào?', EXPECTED_E, True),
    EvalQuestion('E04', 'E', 'Câu hỏi bẫy chống hallucination', 'Nguyễn Bặc là ai và quê ở đâu?', EXPECTED_E, True),
    EvalQuestion('E05', 'E', 'Câu hỏi bẫy chống hallucination', 'Đinh Điền là ai và có vai trò gì trong triều Đinh?', EXPECTED_E, True),
    EvalQuestion('E06', 'E', 'Câu hỏi bẫy chống hallucination', 'Lê Hoàn có quan hệ như thế nào với nhà Đinh?', EXPECTED_E, True),
    EvalQuestion('E07', 'E', 'Câu hỏi bẫy chống hallucination', 'Phạm Hạp là ai trong thời Đinh?', EXPECTED_E, True),
    EvalQuestion('E08', 'E', 'Câu hỏi bẫy chống hallucination', 'Tứ trụ triều Đinh gồm những ai?', EXPECTED_E, True),
    EvalQuestion('E09', 'E', 'Câu hỏi bẫy chống hallucination', 'Đinh Bộ Lĩnh dẹp loạn 12 sứ quân như thế nào?', EXPECTED_E, True),
    EvalQuestion('E10', 'E', 'Câu hỏi bẫy chống hallucination', 'Sau khi thống nhất đất nước, Đinh Bộ Lĩnh đặt quốc hiệu là gì?', EXPECTED_E, True),
    EvalQuestion('Q01', 'Q', 'Bộ 10 câu test nhanh', 'Đại hội VI năm 1986 có ý nghĩa gì đối với lịch sử Việt Nam?', EXPECTED_Q, False),
    EvalQuestion('Q02', 'Q', 'Bộ 10 câu test nhanh', 'Trước Đổi mới, nền kinh tế Việt Nam gặp những khó khăn lớn nào?', EXPECTED_Q, False),
    EvalQuestion('Q03', 'Q', 'Bộ 10 câu test nhanh', 'Chính sách Đổi mới đã thay đổi cơ chế quản lý kinh tế ở Việt Nam như thế nào?', EXPECTED_Q, False),
    EvalQuestion('Q04', 'Q', 'Bộ 10 câu test nhanh', 'Vì sao Việt Nam phải chuyển sang nền kinh tế hàng hóa nhiều thành phần?', EXPECTED_Q, False),
    EvalQuestion('Q05', 'Q', 'Bộ 10 câu test nhanh', 'Nông nghiệp Việt Nam thay đổi ra sao sau Đổi mới?', EXPECTED_Q, False),
    EvalQuestion('Q06', 'Q', 'Bộ 10 câu test nhanh', 'Việt Nam bình thường hóa quan hệ với Hoa Kỳ vào năm nào và ý nghĩa là gì?', EXPECTED_Q, False),
    EvalQuestion('Q07', 'Q', 'Bộ 10 câu test nhanh', 'Việt Nam gia nhập ASEAN vào năm nào? Sự kiện này phản ánh thay đổi gì trong chính sách đối ngoại?', EXPECTED_Q, False),
    EvalQuestion('Q08', 'Q', 'Bộ 10 câu test nhanh', 'Đời sống nhân dân Việt Nam thay đổi như thế nào trong giai đoạn 1986–2000?', EXPECTED_Q, False),
    EvalQuestion('Q09', 'Q', 'Bộ 10 câu test nhanh', 'Những hạn chế của công cuộc Đổi mới trong giai đoạn đầu là gì?', EXPECTED_Q, False),
    EvalQuestion('Q10', 'Q', 'Bộ 10 câu test nhanh', 'Đinh Bộ Lĩnh là ai và dưới trướng ông có những tướng nào?', EXPECTED_Q, True),
]


def load_env() -> None:
    load_dotenv(ROOT_DIR / '.env')
    load_dotenv(RAG_API_DIR / '.env', override=True)


def normalize_for_matching(text: str) -> str:
    normalized = unicodedata.normalize('NFD', (text or '').lower())
    normalized = ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
    normalized = normalized.replace('đ', 'd')
    normalized = normalized.replace('–', '-').replace('—', '-')
    return re.sub(r'\s+', ' ', normalized).strip()


def compact(text: str, limit: int = 260) -> str:
    value = re.sub(r'\s+', ' ', text or '').strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + '...'


def has_vietnamese_diacritics(text: str) -> bool:
    lowered = text or ''
    if any(ch in DIACRITIC_CHARS for ch in lowered.lower()):
        return True
    return any(word in lowered for word in DIACRITIC_WORDS)


def contains_any_marker(text: str, markers: tuple[str, ...]) -> bool:
    normalized = normalize_for_matching(text)
    return any(normalize_for_matching(marker) in normalized for marker in markers)


def contains_old_non_diacritic_phrase(text: str) -> bool:
    lowered = (text or '').lower()
    return any(phrase.lower() in lowered for phrase in OLD_NON_DIACRITIC_PHRASES)


def answer_mentions_sources(text: str) -> bool:
    normalized = normalize_for_matching(text or '')
    return any(marker in normalized for marker in ('nguon:', '[nguon', 'source:', '[source'))


def contains_refusal_phrase(text: str) -> bool:
    return contains_any_marker(text, REFUSAL_MARKERS)


def contains_refusal_scope(text: str) -> bool:
    return contains_any_marker(text, REFUSAL_SCOPE_MARKERS)


def is_controlled_refusal(text: str) -> bool:
    if contains_any_marker(text, ('tài liệu hiện tại không chứa thông tin', 'tài liệu hiện tại không chứa đủ thông tin', 'cần bổ sung tài liệu')):
        return True
    return contains_refusal_phrase(text) and contains_refusal_scope(text)


def is_weak_refusal(text: str) -> bool:
    return contains_refusal_phrase(text) and not is_controlled_refusal(text)


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def db_config() -> dict[str, Any]:
    return {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USERNAME', 'raguser'),
        'password': os.getenv('DB_PASSWORD', 'ragpass'),
        'database': os.getenv('DB_DATABASE', 'rag'),
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
        'connect_timeout': int(os.getenv('DB_CONNECT_TIMEOUT', '5')),
        'read_timeout': int(os.getenv('DB_READ_TIMEOUT', '10')),
        'write_timeout': int(os.getenv('DB_WRITE_TIMEOUT', '10')),
    }


def to_api_uuid(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)) and len(value) == 16:
        return str(uuid.UUID(bytes=bytes(value)))
    return str(value)


def discover_latest_document() -> tuple[str, str]:
    query = """
        SELECT id, user_id, file_name, total_chunks, status, updated_at
        FROM documents
        WHERE total_chunks IS NULL OR total_chunks > 0
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
    """
    try:
        with pymysql.connect(**db_config()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError(MISSING_DOCUMENT_MESSAGE) from exc

    if not row:
        raise RuntimeError(MISSING_DOCUMENT_MESSAGE)

    print(
        '[setup] using latest document: '
        f'fileName={row.get("file_name")} status={row.get("status")} chunks={row.get("total_chunks")}',
        flush=True,
    )
    return to_api_uuid(row['user_id']), to_api_uuid(row['id'])


def discover_user_for_document(document_id: str) -> str:
    query = """
        SELECT user_id, file_name, total_chunks, status
        FROM documents
        WHERE id = uuid_to_bin(%s) OR id = %s
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
    """
    try:
        with pymysql.connect(**db_config()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (document_id, document_id))
                row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError(
            'Cannot run batch evaluation: missing userId. Set SMOKE_USER_ID, '
            'or make MySQL available so the script can look up the document owner.'
        ) from exc

    if not row:
        raise RuntimeError(
            'Cannot run batch evaluation: missing userId. Set SMOKE_USER_ID, '
            'or verify SMOKE_DOCUMENT_ID exists in MySQL.'
        )

    print(
        '[setup] using document owner from MySQL: '
        f'fileName={row.get("file_name")} status={row.get("status")} chunks={row.get("total_chunks")}',
        flush=True,
    )
    return to_api_uuid(row['user_id'])


def resolve_ids(args: argparse.Namespace) -> tuple[str, str]:
    user_id = args.user_id or os.getenv('SMOKE_USER_ID')
    document_id = args.document_id or os.getenv('SMOKE_DOCUMENT_ID')
    if user_id and document_id:
        return user_id, document_id
    if document_id and not user_id:
        return discover_user_for_document(document_id), document_id
    return discover_latest_document()


def check_api_running(base_url: str) -> bool:
    try:
        response = requests.get(f'{base_url.rstrip("/")}/health', timeout=5)
        return response.status_code < 500
    except requests.RequestException:
        return False


def source_value(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None:
            return value
    return None


def normalize_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        'fileName': source_value(source, 'fileName', 'file_name'),
        'pageNumber': source_value(source, 'pageNumber', 'page_start', 'page'),
        'pageEnd': source_value(source, 'pageEnd', 'page_end'),
        'chunkIndex': source_value(source, 'chunkIndex', 'chunk_index'),
        'score': source_value(source, 'score', 'final_score'),
        'supportLevel': source_value(source, 'supportLevel', 'support_level'),
        'chunkId': source_value(source, 'chunkId', 'chunk_id'),
        'preview': source.get('preview'),
    }


def raw_source_candidates(raw_response: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    for field in ('sources', 'citations', 'source_documents', 'related_chunks'):
        value = raw_response.get(field) or []
        if isinstance(value, list) and value:
            return value, field
    return [], None


def response_preview(response: requests.Response) -> str:
    return compact(response.text, 300)


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def retry_delay_seconds(response: requests.Response | None, attempt_index: int) -> float:
    if response is not None and response.status_code == 429:
        retry_after = parse_retry_after(response.headers.get('Retry-After'))
        if retry_after is not None:
            return retry_after
        return float([30, 60, 120][min(attempt_index, 2)])
    return float(min(5 * (2 ** attempt_index), 60))


def ask_with_retries(
    base_url: str,
    user_id: str,
    document_id: str,
    question: EvalQuestion,
    request_timeout: int,
    max_retries: int,
    stop_on_rate_limit: bool,
) -> AskResult:
    message_id = f'eval-{question.question_id.lower()}-{uuid.uuid4().hex}'
    payload = {
        'user_id': user_id,
        'document_id': document_id,
        'session_id': SESSION_ID,
        'message_id': message_id,
        'question': question.question,
    }
    url = f'{base_url.rstrip("/")}/rag/ask'
    total_start = time.perf_counter()
    total_attempts = max_retries + 1
    saw_rate_limit = False

    for attempt_index in range(total_attempts):
        attempt_number = attempt_index + 1
        try:
            response = requests.post(url, json=payload, timeout=request_timeout)
            latency_ms = int((time.perf_counter() - total_start) * 1000)

            if response.status_code in RETRYABLE_STATUS_CODES:
                saw_rate_limit = saw_rate_limit or response.status_code == 429
                error = (
                    f'HTTP {response.status_code} from RAG API on attempt '
                    f'{attempt_number}/{total_attempts}: {response_preview(response)}'
                )
                if response.status_code == 429 and stop_on_rate_limit:
                    return AskResult({'error': error, '_message_id': message_id}, latency_ms, error, True)
                if attempt_index < max_retries:
                    delay = retry_delay_seconds(response, attempt_index)
                    print(
                        f'  retryable HTTP {response.status_code} on attempt '
                        f'{attempt_number}/{total_attempts}; sleeping {delay:g}s before retry...',
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
                return AskResult({'error': error, '_message_id': message_id}, latency_ms, error, saw_rate_limit)

            response.raise_for_status()
            try:
                data = response.json()
            except ValueError as exc:
                error = f'RAG API returned non-JSON response: {exc}'
                return AskResult({'error': error, '_message_id': message_id}, latency_ms, error, saw_rate_limit)
            data['_message_id'] = message_id
            data['_attempts'] = attempt_number
            return AskResult(data, latency_ms, None, saw_rate_limit)

        except (requests.Timeout, requests.ConnectionError) as exc:
            latency_ms = int((time.perf_counter() - total_start) * 1000)
            error = f'RAG API connection/timeout error on attempt {attempt_number}/{total_attempts}: {exc}'
            if attempt_index < max_retries:
                delay = retry_delay_seconds(None, attempt_index)
                print(
                    f'  connection/timeout on attempt {attempt_number}/{total_attempts}; '
                    f'sleeping {delay:g}s before retry...',
                    flush=True,
                )
                time.sleep(delay)
                continue
            return AskResult({'error': error, '_message_id': message_id}, latency_ms, error, saw_rate_limit)
        except requests.RequestException as exc:
            latency_ms = int((time.perf_counter() - total_start) * 1000)
            error = f'RAG API request failed: {exc}'
            return AskResult({'error': error, '_message_id': message_id}, latency_ms, error, saw_rate_limit)

    latency_ms = int((time.perf_counter() - total_start) * 1000)
    error = 'RAG API request failed after retry loop ended unexpectedly.'
    return AskResult({'error': error, '_message_id': message_id}, latency_ms, error, saw_rate_limit)


def ask_worker(
    queue: mp.Queue,
    base_url: str,
    user_id: str,
    document_id: str,
    question: EvalQuestion,
    request_timeout: int,
    max_retries: int,
    stop_on_rate_limit: bool,
) -> None:
    try:
        result = ask_with_retries(
            base_url,
            user_id,
            document_id,
            question,
            request_timeout,
            max_retries,
            stop_on_rate_limit,
        )
        queue.put(
            {
                'raw_response': result.raw_response,
                'latency_ms': result.latency_ms,
                'error': result.error,
                'rate_limited': result.rate_limited,
            }
        )
    except BaseException as exc:
        queue.put(
            {
                'raw_response': {'error': f'{question.question_id}: worker failed: {exc}'},
                'latency_ms': 0,
                'error': f'{question.question_id}: worker failed: {exc}',
                'rate_limited': False,
            }
        )


def ask_with_deadline(
    base_url: str,
    user_id: str,
    document_id: str,
    question: EvalQuestion,
    request_timeout: int,
    max_retries: int,
    stop_on_rate_limit: bool,
    per_question_timeout: int,
) -> AskResult:
    context = mp.get_context('spawn')
    queue = context.Queue(maxsize=1)
    start = time.perf_counter()
    process = context.Process(
        target=ask_worker,
        args=(
            queue,
            base_url,
            user_id,
            document_id,
            question,
            request_timeout,
            max_retries,
            stop_on_rate_limit,
        ),
    )
    process.start()
    process.join(per_question_timeout)

    if process.is_alive():
        process.terminate()
        process.join(10)
        if process.is_alive():
            process.kill()
            process.join()
        latency_ms = int((time.perf_counter() - start) * 1000)
        error = (
            f'{question.question_id}: per-question timeout exceeded '
            f'after {per_question_timeout}s'
        )
        return AskResult({'error': error}, latency_ms, error, False)

    latency_ms = int((time.perf_counter() - start) * 1000)
    if process.exitcode and queue.empty():
        error = f'{question.question_id}: request worker exited with code {process.exitcode}'
        return AskResult({'error': error}, latency_ms, error, False)

    try:
        payload = queue.get_nowait()
    except Exception:
        error = f'{question.question_id}: request worker returned no result'
        return AskResult({'error': error}, latency_ms, error, False)

    return AskResult(
        payload.get('raw_response') or {},
        int(payload.get('latency_ms') or latency_ms),
        payload.get('error'),
        bool(payload.get('rate_limited')),
    )


def build_checks(
    question: EvalQuestion,
    answer: str,
    sources: list[dict[str, Any]],
    source_mapping_issue: bool = False,
) -> dict[str, Any]:
    has_answer = bool(answer and len(answer.strip()) > 20)
    has_sources = bool(sources)
    vietnamese_diacritics_ok = has_vietnamese_diacritics(answer)
    has_old_non_diacritic_phrase = contains_old_non_diacritic_phrase(answer)
    controlled_refusal = is_controlled_refusal(answer)
    weak_refusal = is_weak_refusal(answer)

    true_hallucination = False
    if question.is_trap and has_answer and not controlled_refusal:
        true_hallucination = contains_any_marker(answer, TRUE_HALLUCINATION_MARKERS) and not contains_refusal_phrase(answer)

    hallucination_risk = bool(true_hallucination)
    if controlled_refusal or weak_refusal:
        hallucination_risk = False

    trap_passed = None
    if question.is_trap:
        trap_passed = bool(controlled_refusal and not hallucination_risk)
        if hallucination_risk:
            trap_passed = False

    return {
        'has_answer': has_answer,
        'has_sources': has_sources,
        'vietnamese_diacritics_ok': vietnamese_diacritics_ok,
        'contains_old_non_diacritic_phrase': has_old_non_diacritic_phrase,
        'source_mapping_issue': source_mapping_issue,
        'controlled_refusal': controlled_refusal,
        'weak_refusal': weak_refusal,
        'true_hallucination': true_hallucination,
        'hallucination_risk': hallucination_risk,
        'trap_passed': trap_passed,
    }


def answer_mentions_missing_info(answer: str) -> bool:
    return contains_any_marker(answer, INSUFFICIENT_INFO_MARKERS)


def choose_verdict(question: EvalQuestion, answer: str, checks: dict[str, Any], error: str | None = None) -> str:
    if error:
        return 'ERROR'

    if question.is_trap:
        if checks['controlled_refusal'] and not checks['hallucination_risk']:
            return 'PASS_TRAP_REFUSAL'
        if checks['weak_refusal'] and not checks['hallucination_risk']:
            return 'WARNING_REFUSAL_WEAK'
        if checks['hallucination_risk']:
            return 'FAIL_HALLUCINATION_RISK'
        return 'WARNING'

    if not checks['has_answer'] or not checks['vietnamese_diacritics_ok'] or checks['contains_old_non_diacritic_phrase']:
        return 'FAIL'
    if not checks['has_sources'] or answer_mentions_missing_info(answer):
        return 'WARNING'
    return 'PASS'


def notes_for_record(question: EvalQuestion, answer: str, checks: dict[str, Any], error: str | None = None) -> list[str]:
    notes: list[str] = []
    if error:
        notes.append(error)
        return notes
    if not checks['has_answer']:
        notes.append('Answer is empty or too short.')
    if not checks['has_sources']:
        notes.append('No sources returned.')
    if checks.get('source_mapping_issue'):
        notes.append('Response sources were empty, but source-like data appeared in related fields or answer text.')
    if not checks['vietnamese_diacritics_ok']:
        notes.append('Answer does not appear to contain Vietnamese diacritics.')
    if checks['contains_old_non_diacritic_phrase']:
        notes.append('Answer contains an old non-diacritic fallback phrase.')
    if question.is_trap:
        if checks['controlled_refusal']:
            notes.append('Trap appears to use controlled refusal.')
        if checks['weak_refusal']:
            notes.append('Trap answer refuses, but does not use the full controlled-refusal format.')
        if checks['hallucination_risk']:
            notes.append('Trap answer includes detailed Đinh/early-medieval-history markers without controlled refusal.')
        if not checks['controlled_refusal'] and not checks['weak_refusal'] and not checks['hallucination_risk']:
            notes.append('Trap refusal is missing or too vague for the simple heuristic.')
    elif answer_mentions_missing_info(answer):
        notes.append('Answer says some information is missing; manual review recommended.')
    return notes


def make_record(
    question: EvalQuestion,
    raw_response: dict[str, Any],
    latency_ms: int,
    error: str | None = None,
) -> dict[str, Any]:
    answer = raw_response.get('answer') or ''
    controlled_trap_refusal = bool(question.is_trap and is_controlled_refusal(answer))
    if controlled_trap_refusal:
        source_items = raw_response.get('sources') or []
        source_field = 'sources' if source_items else None
    else:
        source_items, source_field = raw_source_candidates(raw_response)
    sources = [normalize_source(source) for source in source_items]
    raw_sources_empty = not bool(raw_response.get('sources') or [])
    source_mapping_issue = (not controlled_trap_refusal) and raw_sources_empty and (
        source_field in {'related_chunks', 'citations', 'source_documents'} or answer_mentions_sources(answer)
    )
    checks = build_checks(question, answer, sources, source_mapping_issue)
    verdict = choose_verdict(question, answer, checks, error)
    notes = notes_for_record(question, answer, checks, error)
    return {
        'question_id': question.question_id,
        'group': question.group,
        'group_name': question.group_name,
        'is_trap': question.is_trap,
        'question': question.question,
        'expected_behavior': question.expected_behavior,
        'answer': answer,
        'sources': sources,
        'checks': checks,
        'latency_ms': latency_ms,
        'verdict': verdict,
        'notes': notes,
        'raw_response': raw_response,
    }


QUESTION_BY_ID = {question.question_id: question for question in QUESTIONS}


def reevaluate_record(record: dict[str, Any]) -> dict[str, Any]:
    question = QUESTION_BY_ID.get(str(record.get('question_id')))
    if not question:
        return record

    raw_response = dict(record.get('raw_response') or {})
    raw_response.setdefault('answer', record.get('answer') or '')
    raw_response.setdefault('sources', record.get('sources') or [])
    error = None
    if record.get('verdict') == 'ERROR':
        notes = record.get('notes') or []
        error = notes[0] if notes else raw_response.get('error') or 'Previous ERROR record.'
    return make_record(question, raw_response, int(record.get('latency_ms') or 0), error)


def source_pages(sources: list[dict[str, Any]]) -> str:
    values = []
    for source in sources:
        page = source.get('pageNumber')
        if page is not None:
            values.append(str(page))
    return '|'.join(values)


def source_chunks(sources: list[dict[str, Any]]) -> str:
    values = []
    for source in sources:
        chunk = source.get('chunkIndex')
        if chunk is not None:
            values.append(str(chunk))
    return '|'.join(values)


def sanitize_run_id(run_id: str) -> str:
    safe = re.sub(r'[^A-Za-z0-9_.-]+', '-', run_id.strip())
    safe = safe.strip('.-')
    if not safe:
        raise ValueError('--run-id must contain at least one letter, number, dot, underscore, or hyphen.')
    return safe


def output_paths(output_dir: Path, run_id: str | None) -> tuple[Path, Path, Path]:
    if run_id:
        stem = f'rag_eval_history_{sanitize_run_id(run_id)}'
    else:
        stem = f'rag_eval_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    return (
        output_dir / f'{stem}.txt',
        output_dir / f'{stem}.csv',
        output_dir / f'{stem}.jsonl',
    )


def latest_jsonl_path(output_dir: Path) -> Path | None:
    candidates = sorted(output_dir.glob('rag_eval_history_*.jsonl'), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def find_resume_jsonl_path(output_dir: Path, run_id: str | None) -> Path | None:
    if run_id:
        _, _, jsonl_path = output_paths(output_dir, run_id)
        return jsonl_path if jsonl_path.exists() else None
    return latest_jsonl_path(output_dir)


def records_from_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records
    with path.open('r', encoding='utf-8') as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f'[resume] skipped malformed JSONL line {line_number}: {exc}', file=sys.stderr, flush=True)
                continue
            question_id = record.get('question_id')
            if question_id:
                records[str(question_id)] = reevaluate_record(record)
    return records


def ordered_records(records_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [records_by_id[question.question_id] for question in QUESTIONS if question.question_id in records_by_id]


def parse_groups(groups: str | None) -> set[str] | None:
    if not groups:
        return None
    selected = {item.strip().upper() for item in groups.split(',') if item.strip()}
    valid = {question.group for question in QUESTIONS}
    invalid = sorted(selected - valid)
    if invalid:
        raise ValueError(f'Unknown group(s): {", ".join(invalid)}. Valid groups: {", ".join(sorted(valid))}')
    return selected


def select_questions(groups: str | None, limit: int | None, start_from: str | None) -> list[EvalQuestion]:
    selected_groups = parse_groups(groups)
    selected = [question for question in QUESTIONS if selected_groups is None or question.group in selected_groups]

    if start_from:
        start_from = start_from.strip().upper()
        matching_indexes = [index for index, question in enumerate(selected) if question.question_id.upper() == start_from]
        if not matching_indexes:
            raise ValueError(f'--start-from question_id not found after group filtering: {start_from}')
        selected = selected[matching_indexes[0]:]

    if limit is not None:
        if limit < 0:
            raise ValueError('--limit must be greater than or equal to 0.')
        selected = selected[:limit]

    return selected


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8') as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def initialize_jsonl(path: Path) -> None:
    with path.open('w', encoding='utf-8') as handle:
        handle.flush()
        os.fsync(handle.fileno())


def append_jsonl_record(path: Path, record: dict[str, Any]) -> None:
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        'question_id',
        'group',
        'group_name',
        'is_trap',
        'question',
        'expected_behavior',
        'answer_preview',
        'answer_length',
        'source_count',
        'source_pages',
        'source_chunks',
        'has_answer',
        'has_sources',
        'source_mapping_issue',
        'vietnamese_diacritics_ok',
        'contains_old_non_diacritic_phrase',
        'controlled_refusal',
        'weak_refusal',
        'true_hallucination',
        'hallucination_risk',
        'trap_passed',
        'latency_ms',
        'verdict',
    ]
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            checks = record['checks']
            sources = record['sources']
            writer.writerow(
                {
                    'question_id': record['question_id'],
                    'group': record['group'],
                    'group_name': record['group_name'],
                    'is_trap': record['is_trap'],
                    'question': record['question'],
                    'expected_behavior': record['expected_behavior'],
                    'answer_preview': compact(record['answer'], 260),
                    'answer_length': len(record['answer']),
                    'source_count': len(sources),
                    'source_pages': source_pages(sources),
                    'source_chunks': source_chunks(sources),
                    'has_answer': checks['has_answer'],
                    'has_sources': checks['has_sources'],
                    'source_mapping_issue': checks['source_mapping_issue'],
                    'vietnamese_diacritics_ok': checks['vietnamese_diacritics_ok'],
                    'contains_old_non_diacritic_phrase': checks['contains_old_non_diacritic_phrase'],
                    'controlled_refusal': checks['controlled_refusal'],
                    'weak_refusal': checks['weak_refusal'],
                    'true_hallucination': checks['true_hallucination'],
                    'hallucination_risk': checks['hallucination_risk'],
                    'trap_passed': checks['trap_passed'],
                    'latency_ms': record['latency_ms'],
                    'verdict': record['verdict'],
                }
            )
        handle.flush()
        os.fsync(handle.fileno())


def format_source_line(index: int, source: dict[str, Any]) -> str:
    return (
        f'{index}. fileName={source.get("fileName")}, '
        f'pageNumber={source.get("pageNumber")}, '
        f'chunkIndex={source.get("chunkIndex")}, '
        f'score={source.get("score")}'
    )


def write_txt(path: Path, records: list[dict[str, Any]], generated_at: str, api_url: str, user_id: str, document_id: str) -> None:
    lines: list[str] = [
        'RAG HISTORY EVALUATION REPORT',
        f'Generated at: {generated_at}',
        f'RAG_API_URL: {api_url}',
        f'User ID: {user_id}',
        f'Document ID: {document_id}',
        f'Total questions: {len(records)}',
        '',
    ]

    current_group = None
    for record in records:
        if record['group'] != current_group:
            current_group = record['group']
            lines.extend(
                [
                    '=' * 50,
                    f'[{record["group"]}] {record["group_name"]}',
                    '=' * 50,
                    '',
                ]
            )

        lines.extend(
            [
                f'[{record["question_id"]}] {record["question"]}',
                '',
                'Expected behavior:',
                record['expected_behavior'],
                '',
                'Answer:',
                record['answer'] or '(empty)',
                '',
                'Sources:',
            ]
        )
        if record['sources']:
            for index, source in enumerate(record['sources'], start=1):
                lines.append(format_source_line(index, source))
        else:
            lines.append('(none)')

        checks = record['checks']
        lines.extend(
            [
                '',
                'Auto checks:',
                f'- has_answer: {str(checks["has_answer"]).lower()}',
                f'- has_sources: {str(checks["has_sources"]).lower()}',
                f'- source_mapping_issue: {str(checks["source_mapping_issue"]).lower()}',
                f'- vietnamese_diacritics_ok: {str(checks["vietnamese_diacritics_ok"]).lower()}',
                f'- old_non_diacritic_phrase: {str(checks["contains_old_non_diacritic_phrase"]).lower()}',
                f'- trap_question: {str(record["is_trap"]).lower()}',
                f'- controlled_refusal: {str(checks["controlled_refusal"]).lower()}',
                f'- weak_refusal: {str(checks["weak_refusal"]).lower()}',
                f'- true_hallucination: {str(checks["true_hallucination"]).lower()}',
                f'- hallucination_risk: {str(checks["hallucination_risk"]).lower()}',
                f'- trap_passed: {checks["trap_passed"] if checks["trap_passed"] is not None else "n/a"}',
                f'- latency_ms: {record["latency_ms"]}',
                '',
                'Verdict:',
                record['verdict'],
                '',
                'Notes:',
            ]
        )
        if record['notes']:
            lines.extend(f'- {note}' for note in record['notes'])
        else:
            lines.append('- n/a')
        lines.extend(['', '-' * 50, ''])

    with path.open('w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines))
        handle.flush()
        os.fsync(handle.fileno())


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts = Counter(record['verdict'] for record in records)
    source_coverage = (
        sum(1 for record in records if record['checks']['has_sources']) / len(records)
        if records
        else 0.0
    )
    trap_records = [record for record in records if record['is_trap']]
    trap_pass_rate = (
        sum(1 for record in trap_records if record['checks']['trap_passed']) / len(trap_records)
        if trap_records
        else 0.0
    )
    vietnamese_pass_rate = (
        sum(1 for record in records if record['checks']['vietnamese_diacritics_ok']) / len(records)
        if records
        else 0.0
    )
    avg_latency_ms = (
        round(sum(record['latency_ms'] for record in records) / len(records), 2)
        if records
        else 0.0
    )
    return {
        'total_questions': len(records),
        'verdicts': verdicts,
        'source_coverage': source_coverage,
        'source_mapping_issue_count': sum(1 for record in records if record['checks'].get('source_mapping_issue')),
        'trap_pass_rate': trap_pass_rate,
        'hallucination_risk_count': sum(1 for record in records if record['checks']['hallucination_risk']),
        'vietnamese_diacritics_pass_rate': vietnamese_pass_rate,
        'avg_latency_ms': avg_latency_ms,
    }


def print_summary(summary: dict[str, Any], txt_path: Path, csv_path: Path, jsonl_path: Path) -> None:
    verdicts: Counter = summary['verdicts']
    print('\nEvaluation Summary')
    print(f'Total questions: {summary["total_questions"]}')
    print(f'PASS: {verdicts.get("PASS", 0)}')
    print(f'WARNING: {verdicts.get("WARNING", 0)}')
    print(f'FAIL: {verdicts.get("FAIL", 0)}')
    print(f'PASS_TRAP_REFUSAL: {verdicts.get("PASS_TRAP_REFUSAL", 0)}')
    print(f'WARNING_REFUSAL_WEAK: {verdicts.get("WARNING_REFUSAL_WEAK", 0)}')
    print(f'FAIL_HALLUCINATION_RISK: {verdicts.get("FAIL_HALLUCINATION_RISK", 0)}')
    print(f'ERROR: {verdicts.get("ERROR", 0)}')
    print(f'Source coverage: {summary["source_coverage"]:.2%}')
    print(f'Source mapping issue count: {summary["source_mapping_issue_count"]}')
    print(f'Trap pass rate: {summary["trap_pass_rate"]:.2%}')
    print(f'Vietnamese diacritics pass rate: {summary["vietnamese_diacritics_pass_rate"]:.2%}')
    print(f'Hallucination risk count: {summary["hallucination_risk_count"]}')
    print(f'Average latency: {summary["avg_latency_ms"]} ms')
    print(f'Output TXT: {txt_path}')
    print(f'Output CSV: {csv_path}')
    print(f'Output JSONL: {jsonl_path}')


def regenerate_from_jsonl(jsonl_path: Path) -> int:
    if not jsonl_path.exists():
        print(f'JSONL file not found: {jsonl_path}', file=sys.stderr, flush=True)
        return 2

    records_by_id = records_from_jsonl(jsonl_path)
    records = ordered_records(records_by_id)
    txt_path = jsonl_path.with_suffix('.txt')
    csv_path = jsonl_path.with_suffix('.csv')
    generated_at = datetime.now().isoformat(timespec='seconds')

    write_jsonl(jsonl_path, records)
    write_txt(txt_path, records, generated_at, 'from-jsonl', 'from-jsonl', 'from-jsonl')
    write_csv(csv_path, records)
    print_summary(summarize(records), txt_path, csv_path, jsonl_path)
    return 1 if any(record['verdict'] in {'FAIL', 'FAIL_HALLUCINATION_RISK', 'ERROR'} for record in records) else 0


def run() -> int:
    load_env()
    parser = argparse.ArgumentParser(description='Batch-evaluate the RAG API with Vietnamese history questions.')
    parser.add_argument('--api-url', default=os.getenv('RAG_API_URL', 'http://localhost:8001'))
    parser.add_argument('--user-id', default=os.getenv('SMOKE_USER_ID'))
    parser.add_argument('--document-id', default=os.getenv('SMOKE_DOCUMENT_ID'))
    parser.add_argument('--output-dir', default=str(OUTPUT_DIR))
    parser.add_argument('--run-id')
    parser.add_argument('--groups', help='Comma-separated groups to run, e.g. Q, E, or A,B,C.')
    parser.add_argument('--limit', type=int, help='Limit the number of selected questions after group filtering.')
    parser.add_argument('--start-from', help='Skip selected questions until this question_id is reached, e.g. C01.')
    parser.add_argument('--from-jsonl', help='Regenerate TXT/CSV reports from an existing JSONL checkpoint without calling the RAG API.')
    parser.add_argument('--retry-errors', action='store_true', help='When resuming, re-run records whose current verdict is ERROR.')
    parser.add_argument('--max-retries', type=int, default=int(os.getenv('EVAL_MAX_RETRIES', '3')))
    parser.add_argument(
        '--request-timeout',
        type=int,
        default=int(os.getenv('EVAL_TIMEOUT_SECONDS', os.getenv('RAG_EVAL_REQUEST_TIMEOUT', '120'))),
    )
    parser.add_argument(
        '--per-question-timeout',
        type=int,
        default=int(os.getenv('EVAL_PER_QUESTION_TIMEOUT_SECONDS', '90')),
        help='Hard timeout for one question, including retries/backoff.',
    )
    parser.add_argument('--request-delay', type=float, default=float(os.getenv('EVAL_REQUEST_DELAY_SECONDS', '3')))
    parser.add_argument('--stop-on-rate-limit', action='store_true', default=parse_bool(os.getenv('EVAL_STOP_ON_RATE_LIMIT'), False))
    parser.add_argument('--resume', action='store_true', default=parse_bool(os.getenv('EVAL_RESUME'), False))
    args = parser.parse_args()

    if args.from_jsonl:
        return regenerate_from_jsonl(Path(args.from_jsonl))

    try:
        selected_questions = select_questions(args.groups, args.limit, args.start_from)
    except ValueError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 2

    if not check_api_running(args.api_url):
        print('Batch evaluation script created but not executed because RAG API is not running.', file=sys.stderr, flush=True)
        print('Start it with:', file=sys.stderr, flush=True)
        print('uvicorn app.main:app --reload --port 8001', file=sys.stderr, flush=True)
        print('Then run:', file=sys.stderr, flush=True)
        print('python scripts/batch_eval_history_rag.py', file=sys.stderr, flush=True)
        return 2

    try:
        user_id, document_id = resolve_ids(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_records_by_id: dict[str, dict[str, Any]] = {}
    resume_path = find_resume_jsonl_path(output_dir, args.run_id) if args.resume else None
    if resume_path:
        jsonl_path = resume_path
        txt_path = resume_path.with_suffix('.txt')
        csv_path = resume_path.with_suffix('.csv')
        existing_records_by_id = records_from_jsonl(jsonl_path)
        print(f'[resume] loaded {len(existing_records_by_id)} existing records from {jsonl_path}', flush=True)
    elif args.resume and args.run_id:
        txt_path, csv_path, jsonl_path = output_paths(output_dir, args.run_id)
        print(f'[resume] no existing JSONL for run-id {args.run_id}; starting {jsonl_path}', flush=True)
        initialize_jsonl(jsonl_path)
    elif args.resume and not args.run_id:
        checkpoint_path = latest_jsonl_path(output_dir)
        if not checkpoint_path:
            print(f'[resume] no JSONL checkpoint found in {output_dir}', file=sys.stderr, flush=True)
            return 2
        jsonl_path = checkpoint_path
        txt_path = checkpoint_path.with_suffix('.txt')
        csv_path = checkpoint_path.with_suffix('.csv')
        existing_records_by_id = records_from_jsonl(jsonl_path)
        print(f'[resume] loaded {len(existing_records_by_id)} existing records from {jsonl_path}', flush=True)
    else:
        txt_path, csv_path, jsonl_path = output_paths(output_dir, args.run_id)
        initialize_jsonl(jsonl_path)
    generated_at = datetime.now().isoformat(timespec='seconds')

    records_by_id: dict[str, dict[str, Any]] = dict(existing_records_by_id)
    records = ordered_records(records_by_id)
    print(f'[setup] writing progressive outputs to {output_dir}', flush=True)
    print(
        '[setup] '
        f'timeout={args.request_timeout}s max_retries={args.max_retries} '
        f'per_question_timeout={args.per_question_timeout}s '
        f'delay={args.request_delay:g}s stop_on_rate_limit={args.stop_on_rate_limit} resume={args.resume} '
        f'retry_errors={args.retry_errors} run_id={args.run_id or "timestamp"} groups={args.groups or "all"} '
        f'limit={args.limit} start_from={args.start_from}',
        flush=True,
    )
    write_jsonl(jsonl_path, records)
    write_txt(txt_path, records, generated_at, args.api_url, user_id, document_id)
    write_csv(csv_path, records)

    total_selected = len(selected_questions)
    for index, question in enumerate(selected_questions, start=1):
        existing_record = records_by_id.get(question.question_id)
        if existing_record and not (args.retry_errors and existing_record.get('verdict') == 'ERROR'):
            print(f'[{index}/{total_selected}] {question.question_id} - skipped (resume)', flush=True)
            continue
        if existing_record and args.retry_errors and existing_record.get('verdict') == 'ERROR':
            print(f'[{index}/{total_selected}] {question.question_id} - retrying previous ERROR...', flush=True)

        print(f'[{index}/{total_selected}] {question.question_id} - asking...', flush=True)
        result = ask_with_deadline(
            args.api_url,
            user_id,
            document_id,
            question,
            args.request_timeout,
            args.max_retries,
            args.stop_on_rate_limit,
            args.per_question_timeout,
        )
        record = make_record(question, result.raw_response, result.latency_ms, result.error)
        records_by_id[question.question_id] = record
        append_jsonl_record(jsonl_path, record)
        records = ordered_records(records_by_id)
        write_jsonl(jsonl_path, records)
        write_txt(txt_path, records, generated_at, args.api_url, user_id, document_id)
        write_csv(csv_path, records)
        if result.error:
            print(f'[{index}/{total_selected}] {question.question_id} - ERROR in {result.latency_ms}ms: {result.error}', flush=True)
        else:
            print(f'[{index}/{total_selected}] {question.question_id} - done in {result.latency_ms}ms', flush=True)
        print(f'  verdict={record["verdict"]} sources={len(record["sources"])}', flush=True)

        if result.rate_limited and args.stop_on_rate_limit:
            print('[stop] HTTP 429 received and EVAL_STOP_ON_RATE_LIMIT=true; stopping batch early.', flush=True)
            break

        if index < total_selected and args.request_delay > 0:
            print(f'Sleeping {args.request_delay:g}s before next question...', flush=True)
            time.sleep(args.request_delay)

    write_txt(txt_path, records, generated_at, args.api_url, user_id, document_id)
    write_csv(csv_path, records)
    print_summary(summarize(records), txt_path, csv_path, jsonl_path)

    return 1 if any(record['verdict'] in {'FAIL', 'FAIL_HALLUCINATION_RISK', 'ERROR'} for record in records) else 0


if __name__ == '__main__':
    raise SystemExit(run())
