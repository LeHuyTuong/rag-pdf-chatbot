package com.example.ragchatbot.document.dto;

public record FileMetadata(
		String originalFileName,
		String storedFileName,
		String filePath,
		String contentType,
		long size
) {
}
