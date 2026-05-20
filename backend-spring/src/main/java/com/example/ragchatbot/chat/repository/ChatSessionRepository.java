package com.example.ragchatbot.chat.repository;

import com.example.ragchatbot.chat.entity.ChatSession;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ChatSessionRepository extends JpaRepository<ChatSession, UUID> {
	List<ChatSession> findByUserIdOrderByUpdatedAtDesc(UUID userId);
	Optional<ChatSession> findByIdAndUserId(UUID id, UUID userId);
	Optional<ChatSession> findFirstByUserIdAndDocumentIdOrderByUpdatedAtDesc(UUID userId, UUID documentId);
	long countByUserId(UUID userId);
}
