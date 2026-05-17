package com.example.ragchatbot.chat.exception;

import java.util.UUID;

public class ChatNotFoundException extends RuntimeException {
	public ChatNotFoundException(UUID id) {
		super("Chat session not found: " + id);
	}
}
