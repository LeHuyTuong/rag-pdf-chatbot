package com.example.ragchatbot.document.service;

import com.example.ragchatbot.document.dto.FileMetadata;
import com.example.ragchatbot.document.exception.FileStorageException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.nio.file.Files;
import java.nio.file.Path;
import java.text.Normalizer;
import java.util.Locale;
import java.util.Objects;
import java.util.UUID;

@Service
public class FileStorageService {
	private final Path storage;

	public FileStorageService(@Value("${storage.path}") String storagePath) {
		this.storage = Path.of(storagePath);
	}

	public FileMetadata storePdf(MultipartFile file, UUID documentId) {
		String originalName = Objects.requireNonNullElse(file.getOriginalFilename(), "").trim();
		if (file.isEmpty() || !originalName.toLowerCase(Locale.ROOT).endsWith(".pdf")) {
			throw new FileStorageException("Only non-empty PDF files are allowed");
		}

		try {
			Files.createDirectories(storage);
			Path storageRoot = storage.toAbsolutePath().normalize();
			String storedFileName = documentId + "_" + limitFileName(safeFileName(originalName), 180);
			Path targetPath = storageRoot.resolve(storedFileName).normalize();
			if (!targetPath.startsWith(storageRoot)) {
				throw new FileStorageException("Invalid upload path");
			}

			file.transferTo(targetPath);
			if (!Files.exists(targetPath)) {
				throw new FileStorageException("Uploaded file was not written to disk");
			}
			long storedSize = Files.size(targetPath);
			if (storedSize <= 0) {
				throw new FileStorageException("Uploaded PDF is empty after saving");
			}
			return new FileMetadata(originalName, storedFileName, targetPath.toString(), file.getContentType(), storedSize);
		} catch (FileStorageException error) {
			throw error;
		} catch (Exception error) {
			throw new FileStorageException("Failed to store uploaded PDF", error);
		}
	}

	private static String safeFileName(String originalName) {
		String normalized = Normalizer.normalize(originalName, Normalizer.Form.NFC)
				.replaceAll("[\\\\/]+", "_")
				.replaceAll("[\\p{Cntrl}:*?\"<>|]+", "_")
				.replaceAll("\\s+", " ")
				.trim();
		if (normalized.isBlank() || normalized.equals(".pdf")) {
			return "upload.pdf";
		}
		return normalized;
	}

	private static String limitFileName(String name, int maxLength) {
		if (name.length() <= maxLength) {
			return name;
		}
		String extension = "";
		int dot = name.lastIndexOf('.');
		if (dot > 0) {
			extension = name.substring(dot);
			name = name.substring(0, dot);
		}
		int allowedBaseLength = Math.max(1, maxLength - extension.length());
		return name.substring(0, Math.min(name.length(), allowedBaseLength)) + extension;
	}
}
