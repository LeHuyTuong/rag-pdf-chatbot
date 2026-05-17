package com.example.ragchatbot.document.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "documents")
public class Document {
	@Id
	public UUID id = UUID.randomUUID();
	public UUID userId;

	@Column(length = 512)
	public String fileName;

	@Column(length = 512)
	public String originalFileName;

	@Column(length = 1024)
	public String filePath;

	public String fileType = "pdf";
	public String status = "uploaded";
	public Integer totalPages = 0;
	public Integer totalChunks = 0;

	@Column(columnDefinition = "TEXT")
	public String errorMessage;

	public Instant createdAt = Instant.now();
	public Instant updatedAt = Instant.now();
}
