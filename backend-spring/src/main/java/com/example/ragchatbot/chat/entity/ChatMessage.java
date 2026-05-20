package com.example.ragchatbot.chat.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "chat_messages")
public class ChatMessage {
	@Id
	public UUID id = UUID.randomUUID();
	public UUID sessionId;
	public UUID userId;
	public UUID documentId;
	public String role;

	@Column(columnDefinition = "TEXT")
	public String content;

	public BigDecimal confidence;

	@Column(columnDefinition = "TEXT")
	public String sourcesJson;

	@Column(columnDefinition = "TEXT")
	public String relatedChunksJson;

	@Column(columnDefinition = "TEXT")
	public String suggestedQuestionsJson;

	public String answerType;

	public String retrievalReportPath;
	public String answerReportPath;
	public Instant createdAt = Instant.now();
}
