package com.example.ragchatbot.document.controller;

import com.example.ragchatbot.document.dto.DocumentChunkResponse;
import com.example.ragchatbot.document.dto.DocumentResponse;
import com.example.ragchatbot.document.dto.UploadDocumentResponse;
import com.example.ragchatbot.document.service.DocumentService;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/documents")
/**
 * Controller dành cho thao tác liên quan tới Document.
 *
 * Lưu ý: Controller chỉ nhận request và trả response; mọi logic nghiệp vụ nằm trong `DocumentService`.
 */
public class DocumentController {
	private final DocumentService documents;

	public DocumentController(DocumentService documents) {
		this.documents = documents;
	}

	@PostMapping("/upload")
	public UploadDocumentResponse upload(@RequestParam("file") MultipartFile file) {
		return documents.upload(file);
	}

	@GetMapping
	public List<DocumentResponse> list() {
		return documents.list();
	}

	@GetMapping("/{id}")
	public DocumentResponse get(@PathVariable UUID id) {
		return documents.get(id);
	}

	@DeleteMapping("/{id}")
	public void delete(@PathVariable UUID id) {
		documents.delete(id);
	}

	@GetMapping("/{id}/chunks")
	public List<DocumentChunkResponse> chunks(@PathVariable UUID id) {
		return documents.chunks(id);
	}

	@GetMapping("/{id}/chunk-report")
	public Object chunkReport(@PathVariable UUID id) {
		return documents.chunkReport(id);
	}
}
