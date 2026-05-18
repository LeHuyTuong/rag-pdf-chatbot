package com.example.ragchatbot.document.service;

import com.example.ragchatbot.common.security.CurrentUserProvider;
import com.example.ragchatbot.document.client.RagIngestClient;
import com.example.ragchatbot.document.dto.*;
import com.example.ragchatbot.document.entity.Document;
import com.example.ragchatbot.document.entity.DocumentChunk;
import com.example.ragchatbot.document.exception.DocumentNotFoundException;
import com.example.ragchatbot.document.mapper.DocumentMapper;
import com.example.ragchatbot.document.repository.DocumentChunkRepository;
import com.example.ragchatbot.document.repository.DocumentRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
/**
 * Service xử lý upload và lifecycle của Document trong backend.
 *
 * Luồng nghiệp vụ chính của `upload`:
 * 1. Lấy user hiện tại và tạo bản ghi Document với trạng thái `processing`.
 * 2. Gọi `FileStorageService.storePdf` để lưu file lên disk (validate PDF, sanitize tên file).
 * 3. Gọi `RagIngestClient.ingest` để gửi file sang RAG API và chờ kết quả ingest.
 * 4. Cập nhật trạng thái Document theo response từ RAG (completed/failed) và lưu thông tin liên quan.
 *
 * Ghi chú:
 * - Nếu RAG trả lỗi/thất bại, Document sẽ được đánh dấu `failed` và message lỗi được lưu.
 * - Service không trực tiếp parse/chunk/embed; việc đó do RAG API đảm nhận.
 */
public class DocumentService {
	private static final Logger log = LoggerFactory.getLogger(DocumentService.class);
	private final DocumentRepository documents;
	private final DocumentChunkRepository chunks;
	private final FileStorageService storage;
	private final RagIngestClient rag;
	private final DocumentMapper mapper;
	private final CurrentUserProvider currentUser;

	public DocumentService(
			DocumentRepository documents,
			DocumentChunkRepository chunks,
			FileStorageService storage,
			RagIngestClient rag,
			DocumentMapper mapper,
			CurrentUserProvider currentUser
	) {
		this.documents = documents;
		this.chunks = chunks;
		this.storage = storage;
		this.rag = rag;
		this.mapper = mapper;
		this.currentUser = currentUser;
	}

	public UploadDocumentResponse upload(MultipartFile file) {
		UUID userId = currentUser.currentUserId();
		Document document = new Document();
		document.userId = userId;

		FileMetadata metadata = storage.storePdf(file, document.id);
		document.originalFileName = metadata.originalFileName();
		document.fileName = metadata.storedFileName();
		document.filePath = metadata.filePath();
		document.status = "processing";
		documents.save(document);

		log.info(
				"PDF upload saved documentId={} userId={} originalFileName={} storedFileName={} contentType={} storedSize={} path={}",
				document.id, userId, document.originalFileName, document.fileName, metadata.contentType(), metadata.size(), document.filePath);

		try {
			RagIngestResponse response = rag.ingest(new RagIngestRequest(
					userId.toString(),
					document.id.toString(),
					document.filePath,
					document.originalFileName
			));
			applyIngestResponse(document, response);
		} catch (Exception error) {
			document.status = "failed";
			document.errorMessage = error.getMessage();
			log.error("PDF ingest failed documentId={} filePath={}", document.id, document.filePath, error);
		}

		document.updatedAt = Instant.now();
		return mapper.toUploadResponse(documents.save(document));
	}

	public List<DocumentResponse> list() {
		UUID userId = currentUser.currentUserId();
		return documents.findByUserIdOrderByCreatedAtDesc(userId).stream().map(mapper::toResponse).toList();
	}

	public DocumentResponse get(UUID id) {
		return mapper.toResponse(findOwned(id));
	}

	public void delete(UUID id) {
		documents.delete(findOwned(id));
	}

	public List<DocumentChunkResponse> chunks(UUID id) {
		findOwned(id);
		return chunks.findByDocumentIdOrderByChunkIndex(id).stream().map(mapper::toChunkResponse).toList();
	}

	public Object chunkReport(UUID id) {
		Document document = findOwned(id);
		try {
			return rag.chunkReport(id.toString());
		} catch (Exception error) {
			Map<String, Object> fallback = new LinkedHashMap<>();
			fallback.put("document_id", document.id.toString());
			fallback.put("file_name", document.originalFileName);
			fallback.put("file_path", document.filePath);
			fallback.put("status", document.status);
			fallback.put("total_pages", document.totalPages);
			fallback.put("extracted_text_length", 0);
			fallback.put("total_chunks", document.totalChunks);
			fallback.put("parser_used", null);
			fallback.put("error_message", document.errorMessage != null ? document.errorMessage : "Chunk report is not available for this document.");
			fallback.put("report_source", "backend_document_fallback");
			return fallback;
		}
	}

	private Document findOwned(UUID id) {
		return documents.findByIdAndUserId(id, currentUser.currentUserId())
				.orElseThrow(() -> new DocumentNotFoundException(id));
	}

	private void applyIngestResponse(Document document, RagIngestResponse response) {
		if (response == null) {
			document.status = "failed";
			document.errorMessage = "RAG ingest returned an empty response";
			return;
		}
		document.status = response.status() == null ? "failed" : response.status();
		document.totalPages = response.totalPages() == null ? 0 : response.totalPages();
		document.totalChunks = response.totalChunks() == null ? 0 : response.totalChunks();
		document.errorMessage = nullIfBlank(response.errorMessage());
		if (!"completed".equalsIgnoreCase(document.status)) {
			if (document.errorMessage == null) {
				document.errorMessage = nullIfBlank(response.warning());
			}
			if (document.errorMessage == null) {
				document.errorMessage = "RAG ingest returned status=" + document.status;
			}
			log.warn(
					"RAG ingest did not complete documentId={} status={} pages={} chunks={} error={}",
					document.id, document.status, document.totalPages, document.totalChunks, document.errorMessage);
		} else {
			log.info(
					"RAG ingest completed documentId={} pages={} chunks={} parser={} textLength={}",
					document.id, document.totalPages, document.totalChunks, response.parserUsed(), response.extractedTextLength());
		}
	}

	private static String nullIfBlank(String value) {
		return value == null || value.isBlank() ? null : value;
	}
}
