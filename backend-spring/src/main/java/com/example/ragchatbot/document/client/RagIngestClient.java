package com.example.ragchatbot.document.client;

import com.example.ragchatbot.document.dto.RagIngestRequest;
import com.example.ragchatbot.document.dto.RagIngestResponse;
import com.example.ragchatbot.document.exception.RagIngestException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Component
public class RagIngestClient {
	private final RestTemplate rest;
	private final String url;

	public RagIngestClient(RestTemplate rest, @Value("${rag.api.url}") String url) {
		this.rest = rest;
		this.url = url;
	}

	public RagIngestResponse ingest(RagIngestRequest request) {
		try {
			return rest.postForObject(url + "/documents/ingest", request, RagIngestResponse.class);
		} catch (Exception error) {
			throw new RagIngestException("Failed to call RAG ingest API", error);
		}
	}

	public Object chunkReport(String documentId) {
		return rest.getForObject(url + "/debug/documents/" + documentId + "/chunk-report", Object.class);
	}
}
