package com.example.ragchatbot.common.web;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class RootHealthController {
	@GetMapping("/")
	Map<String, String> root() {
		return Map.of("status", "ok", "service", "backend-spring", "health", "/health");
	}

	@GetMapping("/health")
	Map<String, String> simpleHealth() {
		return Map.of("status", "ok");
	}

	@GetMapping("/actuator/health")
	Map<String, String> health() {
		return Map.of("status", "UP");
	}
}
