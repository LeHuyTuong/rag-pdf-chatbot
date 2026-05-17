package com.example.ragchatbot.document.dto;

import java.time.Instant;
import java.util.UUID;

public record DocumentChunkResponse(
		UUID id,
		UUID documentId,
		UUID userId,
		String fileName,
		Integer chunkIndex,
		Integer pageStart,
		Integer pageEnd,
		Integer charStart,
		Integer charEnd,
		Integer tokenCount,
		String content,
		String chunkReason,
		String qdrantPointId,
		Instant createdAt
) {
}
