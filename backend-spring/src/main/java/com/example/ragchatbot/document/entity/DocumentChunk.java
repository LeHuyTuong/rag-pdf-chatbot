package com.example.ragchatbot.document.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "document_chunks")
public class DocumentChunk {
	@Id
	public UUID id;
	public UUID documentId;
	public UUID userId;

	@Column(length = 512)
	public String fileName;

	public Integer chunkIndex;
	public Integer pageStart;
	public Integer pageEnd;
	public Integer charStart;
	public Integer charEnd;
	public Integer tokenCount;

	@Column(columnDefinition = "TEXT")
	public String content;

	@Column(columnDefinition = "TEXT")
	public String chunkReason;

	public String qdrantPointId;
	public Instant createdAt = Instant.now();
}
