package com.example.ragchatbot.document.dto;

import java.time.Instant;
import java.util.UUID;

public record DocumentResponse(
		UUID id,
		UUID userId,
		String fileName,
		String originalFileName,
		String filePath,
		String fileType,
		String status,
		Integer totalPages,
		Integer totalChunks,
		String errorMessage,
		Instant createdAt,
		Instant updatedAt
) {
}
