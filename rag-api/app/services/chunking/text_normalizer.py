import re


class TextNormalizer:
    def normalize(self, text: str) -> str:
        text = text.replace('\x00', ' ')
        text = re.sub(r'[ \t\r\f\v]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n', text)
        return text.strip()
