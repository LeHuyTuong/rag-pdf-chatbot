package com.example.ragchatbot.chat.repository;

import com.example.ragchatbot.chat.entity.ChatMessage;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, UUID> {
	List<ChatMessage> findBySessionIdOrderByCreatedAt(UUID sessionId);
	long countByUserId(UUID userId);
}
