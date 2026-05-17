package com.example.ragchatbot.common.web;

import com.example.ragchatbot.chat.repository.ChatMessageRepository;
import com.example.ragchatbot.chat.repository.ChatSessionRepository;
import com.example.ragchatbot.common.security.CurrentUserProvider;
import com.example.ragchatbot.document.repository.DocumentRepository;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api")
public class DashboardController {
	private final DocumentRepository documents;
	private final ChatSessionRepository sessions;
	private final ChatMessageRepository messages;
	private final CurrentUserProvider currentUser;

	public DashboardController(DocumentRepository documents, ChatSessionRepository sessions, ChatMessageRepository messages, CurrentUserProvider currentUser) {
		this.documents = documents;
		this.sessions = sessions;
		this.messages = messages;
		this.currentUser = currentUser;
	}

	@GetMapping("/dashboard")
	Map<String, Long> dashboard() {
		UUID userId = currentUser.currentUserId();
		return Map.of(
				"totalDocuments", (long) documents.findByUserIdOrderByCreatedAtDesc(userId).size(),
				"totalChatSessions", sessions.countByUserId(userId),
				"totalMessages", messages.countByUserId(userId)
		);
	}

	@GetMapping("/health")
	Map<String, String> health() {
		return Map.of("status", "ok");
	}
}
