package com.example.ragchatbot.chat.dto;

import java.time.Instant;
import java.util.UUID;

public record ChatSessionResponse(
		UUID id,
		UUID userId,
		UUID documentId,
		String title,
		Instant createdAt,
		Instant updatedAt
) {
}
