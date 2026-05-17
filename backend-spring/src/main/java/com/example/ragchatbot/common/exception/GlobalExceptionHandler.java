package com.example.ragchatbot.common.exception;

import com.example.ragchatbot.chat.exception.ChatNotFoundException;
import com.example.ragchatbot.document.exception.DocumentNotFoundException;
import com.example.ragchatbot.document.exception.FileStorageException;
import com.example.ragchatbot.document.exception.RagIngestException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.NoSuchElementException;

@RestControllerAdvice
public class GlobalExceptionHandler {
	private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

	@ExceptionHandler({DocumentNotFoundException.class, ChatNotFoundException.class, NoSuchElementException.class})
	public ResponseEntity<ApiError> notFound(RuntimeException error) {
		return ResponseEntity.status(HttpStatus.NOT_FOUND)
				.body(ApiError.of("Resource not found", error.getMessage(), "NOT_FOUND"));
	}

	@ExceptionHandler({BadCredentialsException.class, SecurityException.class})
	public ResponseEntity<ApiError> unauthorized(RuntimeException error) {
		return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
				.body(ApiError.of("Unauthorized", error.getMessage(), "UNAUTHORIZED"));
	}

	@ExceptionHandler(FileStorageException.class)
	public ResponseEntity<ApiError> fileStorage(FileStorageException error) {
		return ResponseEntity.status(HttpStatus.BAD_REQUEST)
				.body(ApiError.of("File upload failed", error.getMessage(), "FILE_STORAGE_ERROR"));
	}

	@ExceptionHandler(RagIngestException.class)
	public ResponseEntity<ApiError> ragIngest(RagIngestException error) {
		return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
				.body(ApiError.of("RAG service failed", error.getMessage(), "RAG_INGEST_ERROR"));
	}

	@ExceptionHandler(IllegalArgumentException.class)
	public ResponseEntity<ApiError> badRequest(IllegalArgumentException error) {
		return ResponseEntity.status(HttpStatus.BAD_REQUEST)
				.body(ApiError.of("Bad request", error.getMessage(), "BAD_REQUEST"));
	}

	@ExceptionHandler(Exception.class)
	public ResponseEntity<ApiError> unexpected(Exception error) {
		log.error("Unhandled backend error", error);
		return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
				.body(ApiError.of("Internal server error", "Unexpected backend error", "INTERNAL_ERROR"));
	}
}
