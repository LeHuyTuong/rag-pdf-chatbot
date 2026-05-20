package com.example.ragchatbot.chat.mapper;

import com.example.ragchatbot.chat.dto.ChatMessageResponse;
import com.example.ragchatbot.chat.dto.ChatSessionResponse;
import com.example.ragchatbot.chat.entity.ChatMessage;
import com.example.ragchatbot.chat.entity.ChatSession;
import org.springframework.stereotype.Component;

@Component
public class ChatMapper {
	public ChatSessionResponse toSessionResponse(ChatSession session) {
		return new ChatSessionResponse(session.id, session.userId, session.documentId, session.title, session.createdAt, session.updatedAt);
	}

	public ChatMessageResponse toMessageResponse(ChatMessage message) {
		return new ChatMessageResponse(
				message.id,
				message.sessionId,
				message.userId,
				message.documentId,
				message.role,
				message.content,
				message.confidence,
				message.sourcesJson,
				message.relatedChunksJson,
				message.suggestedQuestionsJson,
				message.answerType,
				message.retrievalReportPath,
				message.answerReportPath,
				message.createdAt
		);
	}
}
