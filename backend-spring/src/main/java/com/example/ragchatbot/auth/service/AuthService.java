package com.example.ragchatbot.auth.service;

import com.example.ragchatbot.auth.dto.AuthResponse;
import com.example.ragchatbot.auth.dto.LoginRequest;
import com.example.ragchatbot.auth.dto.RegisterRequest;
import com.example.ragchatbot.auth.security.JwtService;
import com.example.ragchatbot.user.entity.User;
import com.example.ragchatbot.user.repository.UserRepository;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.Instant;

@Service
public class AuthService {
	private final UserRepository users;
	private final PasswordEncoder encoder;
	private final JwtService jwt;

	public AuthService(UserRepository users, PasswordEncoder encoder, JwtService jwt) {
		this.users = users;
		this.encoder = encoder;
		this.jwt = jwt;
	}

	public AuthResponse register(RegisterRequest request) {
		if (request.email() == null || request.email().isBlank()) {
			throw new IllegalArgumentException("Email is required");
		}
		if (request.password() == null || request.password().isBlank()) {
			throw new IllegalArgumentException("Password is required");
		}
		User user = new User();
		user.email = request.email();
		user.fullName = request.fullName();
		user.passwordHash = encoder.encode(request.password());
		users.save(user);
		return new AuthResponse(jwt.create(user.id, user.email), user.id, user.email);
	}

	public AuthResponse login(LoginRequest request) {
		User user = users.findByEmail(request.email())
				.orElseThrow(() -> new BadCredentialsException("Bad credentials"));
		if (!encoder.matches(request.password(), user.passwordHash)) {
			throw new BadCredentialsException("Bad credentials");
		}
		user.updatedAt = Instant.now();
		users.save(user);
		return new AuthResponse(jwt.create(user.id, user.email), user.id, user.email);
	}
}
