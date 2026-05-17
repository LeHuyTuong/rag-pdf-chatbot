package com.example.ragchatbot.document.repository;

import com.example.ragchatbot.document.entity.DocumentChunk;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface DocumentChunkRepository extends JpaRepository<DocumentChunk, UUID> {
	List<DocumentChunk> findByDocumentIdOrderByChunkIndex(UUID documentId);
}
