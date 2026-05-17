package com.example.ragchatbot.chat.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "chat_sessions")
public class ChatSession {
	@Id
	public UUID id = UUID.randomUUID();
	public UUID userId;
	public UUID documentId;
	public String title;
	public Instant createdAt = Instant.now();
	public Instant updatedAt = Instant.now();
}
