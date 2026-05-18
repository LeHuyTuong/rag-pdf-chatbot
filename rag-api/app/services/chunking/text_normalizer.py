import re


class TextNormalizer:
    """
    Bộ chuẩn hóa văn bản nhẹ dùng trước khi chunking hoặc lưu.

    Mục tiêu: loại bỏ ký tự null, gộp whitespace ngang và xóa nhiều dòng trắng liên tiếp.
    """
    def normalize(self, text: str) -> str:
        """
        Trả về text đã chuẩn hóa.
        """
        text = text.replace('\x00', ' ')
        text = re.sub(r'[ \t\r\f\v]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n', text)
        return text.strip()
