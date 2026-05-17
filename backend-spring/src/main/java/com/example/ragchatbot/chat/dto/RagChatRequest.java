package com.example.ragchatbot.chat.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record RagChatRequest(
		@JsonProperty("user_id") String userId,
		@JsonProperty("document_id") String documentId,
		@JsonProperty("session_id") String sessionId,
		@JsonProperty("message_id") String messageId,
		String question
) {
}
