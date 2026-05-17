package com.example.ragchatbot.chat.controller;

import com.example.ragchatbot.chat.client.RagChatClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/debug")
public class DebugController {
	private final RagChatClient rag;

	public DebugController(RagChatClient rag) {
		this.rag = rag;
	}

	@GetMapping("/chat/{messageId}/retrieval-report")
	Object retrieval(@PathVariable String messageId) {
		return rag.get("/debug/chat/" + messageId + "/retrieval-report");
	}

	@GetMapping("/chat/{messageId}/answer-report")
	Object answer(@PathVariable String messageId) {
		return rag.get("/debug/chat/" + messageId + "/answer-report");
	}
}
