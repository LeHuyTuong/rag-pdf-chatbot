package com.example.ragchatbot.user.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "users")
public class User {
	@Id
	public UUID id = UUID.randomUUID();

	@Column(unique = true)
	public String email;

	public String passwordHash;
	public String fullName;
	public String role = "USER";
	public Instant createdAt = Instant.now();
	public Instant updatedAt = Instant.now();
}
