package com.example.ragchatbot.chat.client;

import com.example.ragchatbot.chat.dto.RagChatRequest;
import com.example.ragchatbot.chat.dto.RagChatResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Component
public class RagChatClient {
	private final RestTemplate rest;
	private final String url;

	public RagChatClient(RestTemplate rest, @Value("${rag.api.url}") String url) {
		this.rest = rest;
		this.url = url;
	}

	public RagChatResponse ask(RagChatRequest request) {
		return rest.postForObject(url + "/rag/ask", request, RagChatResponse.class);
	}

	public Object get(String path) {
		return rest.getForObject(url + path, Object.class);
	}
}
