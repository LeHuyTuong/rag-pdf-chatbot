package com.example.ragchatbot.document.mapper;

import com.example.ragchatbot.document.dto.DocumentChunkResponse;
import com.example.ragchatbot.document.dto.DocumentResponse;
import com.example.ragchatbot.document.dto.UploadDocumentResponse;
import com.example.ragchatbot.document.entity.Document;
import com.example.ragchatbot.document.entity.DocumentChunk;
import org.springframework.stereotype.Component;

@Component
public class DocumentMapper {
	public DocumentResponse toResponse(Document document) {
		return new DocumentResponse(
				document.id,
				document.userId,
				document.fileName,
				document.originalFileName,
				document.filePath,
				document.fileType,
				document.status,
				document.totalPages,
				document.totalChunks,
				document.errorMessage,
				document.createdAt,
				document.updatedAt
		);
	}

	public UploadDocumentResponse toUploadResponse(Document document) {
		return new UploadDocumentResponse(
				document.id,
				document.userId,
				document.fileName,
				document.originalFileName,
				document.filePath,
				document.fileType,
				document.status,
				document.totalPages,
				document.totalChunks,
				document.errorMessage,
				document.createdAt,
				document.updatedAt
		);
	}

	public DocumentChunkResponse toChunkResponse(DocumentChunk chunk) {
		return new DocumentChunkResponse(
				chunk.id,
				chunk.documentId,
				chunk.userId,
				chunk.fileName,
				chunk.chunkIndex,
				chunk.pageStart,
				chunk.pageEnd,
				chunk.charStart,
				chunk.charEnd,
				chunk.tokenCount,
				chunk.content,
				chunk.chunkReason,
				chunk.qdrantPointId,
				chunk.createdAt
		);
	}
}
