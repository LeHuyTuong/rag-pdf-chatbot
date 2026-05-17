package com.example.ragchatbot.chat.dto;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record ChatMessageResponse(
		UUID id,
		UUID sessionId,
		UUID userId,
		UUID documentId,
		String role,
		String content,
		BigDecimal confidence,
		String sourcesJson,
		String retrievalReportPath,
		String answerReportPath,
		Instant createdAt
) {
}
