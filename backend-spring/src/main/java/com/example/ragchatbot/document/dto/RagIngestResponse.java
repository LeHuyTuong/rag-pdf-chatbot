package com.example.ragchatbot.document.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record RagIngestResponse(
		@JsonProperty("document_id") String documentId,
		String status,
		@JsonProperty("total_pages") Integer totalPages,
		@JsonProperty("total_chunks") Integer totalChunks,
		@JsonProperty("chunk_report_path") String chunkReportPath,
		@JsonProperty("extracted_text_length") Integer extractedTextLength,
		@JsonProperty("parser_used") String parserUsed,
		@JsonProperty("error_message") String errorMessage,
		String warning
) {
}
