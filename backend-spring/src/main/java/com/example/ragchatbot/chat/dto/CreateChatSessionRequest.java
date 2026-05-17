package com.example.ragchatbot.chat.dto;

import java.util.UUID;

public record CreateChatSessionRequest(UUID documentId, String title) {
}
