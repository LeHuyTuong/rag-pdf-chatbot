package com.example.ragchatbot.chat.controller;

import com.example.ragchatbot.chat.dto.*;
import com.example.ragchatbot.chat.service.ChatService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/chat")
public class ChatController {
	private final ChatService chat;

	public ChatController(ChatService chat) {
		this.chat = chat;
	}

	@PostMapping("/sessions")
	ChatSessionResponse create(@RequestBody CreateChatSessionRequest request) {
		return chat.createSession(request);
	}

	@GetMapping("/sessions")
	List<ChatSessionResponse> list() {
		return chat.listSessions();
	}

	@GetMapping("/sessions/{id}/messages")
	List<ChatMessageResponse> messages(@PathVariable UUID id) {
		return chat.messages(id);
	}

	@PostMapping("/ask")
	ChatAskResponse ask(@RequestBody AskQuestionRequest request) {
		return chat.ask(request);
	}
}
