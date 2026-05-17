from app.infrastructure.mysql.mysql_service import MySqlService


class ChunkRepository:
    def __init__(self, mysql: MySqlService):
        self.mysql = mysql

    def save_all(self, chunks):
        return self.mysql.save_chunks(chunks)

    def find_by_document_id(self, document_id: str):
        return self.mysql.get_chunks(document_id)
