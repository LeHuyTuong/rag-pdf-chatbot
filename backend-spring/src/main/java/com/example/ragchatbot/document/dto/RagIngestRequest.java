package com.example.ragchatbot.document.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record RagIngestRequest(
		@JsonProperty("user_id") String userId,
		@JsonProperty("document_id") String documentId,
		@JsonProperty("file_path") String filePath,
		@JsonProperty("file_name") String fileName
) {
}
