import pymysql
from pymysql.cursors import DictCursor
from app.config import Settings
from app.models.schemas import Chunk


class MySqlService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def connect(self):
        return pymysql.connect(autocommit=True, cursorclass=DictCursor, **self.settings.mysql_config)

    def init_schema(self) -> None:
        ddl = '''
        create table if not exists users (
            id varchar(36) primary key,
            email varchar(255) unique,
            password_hash text,
            full_name varchar(255),
            role varchar(64),
            created_at datetime,
            updated_at datetime
        );

        create table if not exists documents (
            id varchar(36) primary key,
            user_id varchar(36),
            file_name varchar(255),
            original_file_name varchar(255),
            file_path varchar(1024),
            file_type varchar(64),
            status varchar(64),
            total_pages int,
            total_chunks int,
            error_message text,
            created_at datetime,
            updated_at datetime
        );

        create table if not exists document_chunks (
            id varchar(36) primary key,
            document_id varchar(36),
            user_id varchar(36),
            file_name varchar(255),
            chunk_index int,
            page_start int,
            page_end int,
            char_start int,
            char_end int,
            token_count int,
            content text,
            chunk_reason text,
            qdrant_point_id varchar(255),
            created_at datetime default current_timestamp
        );

        create table if not exists chat_sessions (
            id varchar(36) primary key,
            user_id varchar(36),
            document_id varchar(36),
            title varchar(255),
            created_at datetime,
            updated_at datetime
        );

        create table if not exists chat_messages (
            id varchar(36) primary key,
            session_id varchar(36),
            user_id varchar(36),
            document_id varchar(36),
            role varchar(64),
            content text,
            confidence decimal(18, 6),
            sources_json text,
            related_chunks_json text,
            suggested_questions_json text,
            answer_type varchar(64),
            retrieval_report_path varchar(1024),
            answer_report_path varchar(1024),
            created_at datetime
        );

        create table if not exists evaluation_runs (
            id varchar(36) primary key,
            user_id varchar(36) null,
            document_id varchar(36) null,
            total_questions int,
            passed int,
            failed int,
            answer_accuracy decimal(18, 6),
            retrieval_hit_rate decimal(18, 6),
            citation_accuracy decimal(18, 6),
            faithfulness_score decimal(18, 6),
            refusal_accuracy decimal(18, 6),
            report_path varchar(1024),
            created_at datetime
        );
        '''
        with self.connect() as conn:
            with conn.cursor() as cur:
                for statement in [s.strip() for s in ddl.split(';') if s.strip()]:
                    cur.execute(statement)
                try:
                    cur.execute('alter table document_chunks add column file_name varchar(255) null after user_id')
                except Exception:
                    pass
                for statement in [
                    'alter table chat_messages add column related_chunks_json text null after sources_json',
                    'alter table chat_messages add column suggested_questions_json text null after related_chunks_json',
                    'alter table chat_messages add column answer_type varchar(64) null after suggested_questions_json',
                ]:
                    try:
                        cur.execute(statement)
                    except Exception:
                        pass

    def save_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        with self.connect() as conn:
            with conn.cursor() as cur:
                for chunk in chunks:
                    values = (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.user_id,
                        chunk.file_name,
                        chunk.chunk_index,
                        chunk.page_start,
                        chunk.page_end,
                        chunk.char_start,
                        chunk.char_end,
                        chunk.token_count,
                        chunk.content,
                        chunk.chunk_reason,
                        chunk.qdrant_point_id,
                    )
                    try:
                        cur.execute(
                            '''
                            insert ignore into document_chunks (
                                id, document_id, user_id, file_name, chunk_index, page_start, page_end,
                                char_start, char_end, token_count, content, chunk_reason, qdrant_point_id
                            ) values (uuid_to_bin(%s), uuid_to_bin(%s), uuid_to_bin(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ''',
                            values,
                        )
                    except Exception:
                        cur.execute(
                            '''
                            insert ignore into document_chunks (
                                id, document_id, user_id, file_name, chunk_index, page_start, page_end,
                                char_start, char_end, token_count, content, chunk_reason, qdrant_point_id
                            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ''',
                            values,
                        )

    def get_chunks(self, document_id: str) -> list[dict]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        '''
                        select bin_to_uuid(id) id, bin_to_uuid(document_id) document_id, bin_to_uuid(user_id) user_id,
                               file_name, chunk_index, page_start, page_end, char_start, char_end, token_count, content,
                               chunk_reason, qdrant_point_id, created_at
                        from document_chunks
                        where document_id=uuid_to_bin(%s)
                        order by chunk_index
                        ''',
                        (document_id,),
                    )
                    return list(cur.fetchall())
                except Exception:
                    cur.execute('select * from document_chunks where document_id=%s order by chunk_index', (document_id,))
                    return list(cur.fetchall())
