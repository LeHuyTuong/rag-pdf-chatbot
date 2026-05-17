package com.example.ragchatbot.auth.security;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;

@Service
public class JwtService {
	private final SecretKey key;
	private final long ttl;

	public JwtService(@Value("${jwt.secret}") String secret, @Value("${jwt.expires-in}") long ttl) {
		this.key = Keys.hmacShaKeyFor(secret.repeat(4).getBytes(StandardCharsets.UTF_8));
		this.ttl = ttl;
	}

	public String create(UUID userId, String email) {
		Instant now = Instant.now();
		return Jwts.builder()
				.subject(userId.toString())
				.claim("email", email)
				.issuedAt(Date.from(now))
				.expiration(Date.from(now.plusMillis(ttl)))
				.signWith(key)
				.compact();
	}

	public UUID userId(String token) {
		return UUID.fromString(Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload().getSubject());
	}
}
