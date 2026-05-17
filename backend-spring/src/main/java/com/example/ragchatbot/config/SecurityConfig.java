package com.example.ragchatbot.config;

import com.example.ragchatbot.auth.security.JwtFilter;
import org.springframework.context.annotation.*;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.*;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
public class SecurityConfig {
	private final JwtFilter filter;

	public SecurityConfig(JwtFilter filter) {
		this.filter = filter;
	}

	@Bean
	SecurityFilterChain chain(HttpSecurity http) throws Exception {
		return http
				.csrf(c -> c.disable())
				.cors(c -> {
				})
				.sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
				.authorizeHttpRequests(a -> a
						.requestMatchers("/", "/health", "/api/auth/**", "/api/health", "/actuator/health").permitAll()
						.anyRequest().authenticated()
				)
				.addFilterBefore(filter, UsernamePasswordAuthenticationFilter.class)
				.build();
	}
}
