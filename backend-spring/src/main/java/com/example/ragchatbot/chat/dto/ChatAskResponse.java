package com.example.ragchatbot.chat.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatAskResponse(
		@JsonProperty("user_message") ChatMessageResponse userMessage,
		@JsonProperty("assistant_message") ChatMessageResponse assistantMessage,
		RagChatResponse answer
) {
}
