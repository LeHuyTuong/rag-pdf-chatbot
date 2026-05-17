package com.example.ragchatbot.common.exception;

import java.time.Instant;

public record ApiError(
		String status,
		String message,
		String detail,
		String errorCode,
		Instant timestamp
) {
	public static ApiError of(String message, String detail, String errorCode) {
		return new ApiError("error", message, detail, errorCode, Instant.now());
	}
}
