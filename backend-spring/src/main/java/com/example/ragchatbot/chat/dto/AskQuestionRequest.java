package com.example.ragchatbot.chat.dto;

import java.util.UUID;

public record AskQuestionRequest(UUID sessionId, UUID documentId, String question) {
}
