package com.example.ragchatbot.chat.service;

import com.example.ragchatbot.chat.client.RagChatClient;
import com.example.ragchatbot.chat.dto.*;
import com.example.ragchatbot.chat.entity.ChatMessage;
import com.example.ragchatbot.chat.entity.ChatSession;
import com.example.ragchatbot.chat.exception.ChatNotFoundException;
import com.example.ragchatbot.chat.mapper.ChatMapper;
import com.example.ragchatbot.chat.repository.ChatMessageRepository;
import com.example.ragchatbot.chat.repository.ChatSessionRepository;
import com.example.ragchatbot.common.security.CurrentUserProvider;
import com.example.ragchatbot.document.exception.DocumentNotFoundException;
import com.example.ragchatbot.document.repository.DocumentRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
public class ChatService {
	private final ChatSessionRepository sessions;
	private final ChatMessageRepository messages;
	private final DocumentRepository documents;
	private final RagChatClient rag;
	private final ChatMapper mapper;
	private final CurrentUserProvider currentUser;
	private final ObjectMapper objectMapper;

	public ChatService(
			ChatSessionRepository sessions,
			ChatMessageRepository messages,
			DocumentRepository documents,
			RagChatClient rag,
			ChatMapper mapper,
			CurrentUserProvider currentUser,
			ObjectMapper objectMapper
	) {
		this.sessions = sessions;
		this.messages = messages;
		this.documents = documents;
		this.rag = rag;
		this.mapper = mapper;
		this.currentUser = currentUser;
		this.objectMapper = objectMapper;
	}

	public ChatSessionResponse createSession(CreateChatSessionRequest request) {
		UUID userId = currentUser.currentUserId();
		ensureOwnedDocument(request.documentId(), userId);
		ChatSession session = new ChatSession();
		session.userId = userId;
		session.documentId = request.documentId();
		session.title = request.title() == null ? "New chat" : request.title();
		return mapper.toSessionResponse(sessions.save(session));
	}

	public List<ChatSessionResponse> listSessions() {
		return sessions.findByUserIdOrderByUpdatedAtDesc(currentUser.currentUserId()).stream().map(mapper::toSessionResponse).toList();
	}

	public List<ChatMessageResponse> messages(UUID sessionId) {
		findOwnedSession(sessionId);
		return messages.findBySessionIdOrderByCreatedAt(sessionId).stream().map(mapper::toMessageResponse).toList();
	}

	public ChatAskResponse ask(AskQuestionRequest request) {
		UUID userId = currentUser.currentUserId();
		ChatSession session = findOwnedSession(request.sessionId());
		ensureOwnedDocument(request.documentId(), userId);

		ChatMessage userMessage = new ChatMessage();
		userMessage.sessionId = session.id;
		userMessage.userId = userId;
		userMessage.documentId = request.documentId();
		userMessage.role = "user";
		userMessage.content = request.question();
		messages.save(userMessage);

		ChatMessage assistantMessage = new ChatMessage();
		assistantMessage.sessionId = session.id;
		assistantMessage.userId = userId;
		assistantMessage.documentId = request.documentId();
		assistantMessage.role = "assistant";

		RagChatResponse ragResponse = rag.ask(new RagChatRequest(
				userId.toString(),
				request.documentId().toString(),
				session.id.toString(),
				assistantMessage.id.toString(),
				request.question()
		));

		assistantMessage.content = ragResponse == null ? "" : ragResponse.answer();
		assistantMessage.confidence = BigDecimal.valueOf(ragResponse == null || ragResponse.confidence() == null ? 0 : ragResponse.confidence());
		assistantMessage.sourcesJson = toJson(ragResponse == null ? null : ragResponse.sources());
		assistantMessage.retrievalReportPath = ragResponse == null ? null : ragResponse.retrievalReportPath();
		assistantMessage.answerReportPath = ragResponse == null ? null : ragResponse.answerReportPath();
		messages.save(assistantMessage);

		session.updatedAt = Instant.now();
		sessions.save(session);
		return new ChatAskResponse(mapper.toMessageResponse(userMessage), mapper.toMessageResponse(assistantMessage), ragResponse);
	}

	private ChatSession findOwnedSession(UUID id) {
		return sessions.findByIdAndUserId(id, currentUser.currentUserId()).orElseThrow(() -> new ChatNotFoundException(id));
	}

	private void ensureOwnedDocument(UUID documentId, UUID userId) {
		documents.findByIdAndUserId(documentId, userId).orElseThrow(() -> new DocumentNotFoundException(documentId));
	}

	private String toJson(Object value) {
		if (value == null) {
			return null;
		}
		try {
			return objectMapper.writeValueAsString(value);
		} catch (JsonProcessingException error) {
			return String.valueOf(value);
		}
	}
}
