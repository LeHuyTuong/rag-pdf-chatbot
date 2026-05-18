package com.example.ragchatbot.common.security;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;

import java.util.UUID;

@Component
/**
 * Trích xuất user id từ SecurityContext hiện tại.
 *
 * Quy ước: Principal được lưu trữ là `UUID` của user; nếu không có authentication hợp lệ thì ném SecurityException.
 */
public class CurrentUserProvider {
	public UUID currentUserId() {
		Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
		if (authentication == null || !(authentication.getPrincipal() instanceof UUID userId)) {
			throw new SecurityException("Authenticated user is required");
		}
		return userId;
	}
}
