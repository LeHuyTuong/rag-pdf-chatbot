package com.example.ragchatbot.document.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.UUID;

public record ChunkReportResponse(
		@JsonProperty("document_id") UUID documentId,
		@JsonProperty("file_name") String fileName,
		@JsonProperty("file_path") String filePath,
		String status,
		@JsonProperty("total_pages") Integer totalPages,
		@JsonProperty("extracted_text_length") Integer extractedTextLength,
		@JsonProperty("total_chunks") Integer totalChunks,
		@JsonProperty("parser_used") String parserUsed,
		@JsonProperty("error_message") String errorMessage,
		@JsonProperty("report_source") String reportSource
) {
}
