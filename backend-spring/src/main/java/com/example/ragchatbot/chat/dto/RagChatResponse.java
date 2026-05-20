package com.example.ragchatbot.chat.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record RagChatResponse(
		String answer,
		Double confidence,
		List<Map<String, Object>> sources,
		@JsonProperty("related_chunks") List<Map<String, Object>> relatedChunks,
		@JsonProperty("suggested_questions") List<String> suggestedQuestions,
		@JsonProperty("answer_type") String answerType,
		String warning,
		@JsonProperty("retrieval_report_path") String retrievalReportPath,
		@JsonProperty("answer_report_path") String answerReportPath
) {
}
