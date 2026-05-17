package com.example.ragchatbot.auth.controller;

import com.example.ragchatbot.auth.dto.AuthResponse;
import com.example.ragchatbot.auth.dto.LoginRequest;
import com.example.ragchatbot.auth.dto.RegisterRequest;
import com.example.ragchatbot.auth.service.AuthService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
	private final AuthService authService;

	public AuthController(AuthService authService) {
		this.authService = authService;
	}

	@PostMapping("/register")
	AuthResponse register(@RequestBody RegisterRequest request) {
		return authService.register(request);
	}

	@PostMapping("/login")
	AuthResponse login(@RequestBody LoginRequest request) {
		return authService.login(request);
	}
}
