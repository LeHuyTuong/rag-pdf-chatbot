package com.example.ragchatbot.config;

import org.springframework.context.annotation.*;
import org.springframework.web.servlet.config.annotation.*;

@Configuration
public class CorsConfig implements WebMvcConfigurer {
	@Override
	public void addCorsMappings(CorsRegistry r) {
		r.addMapping("/**").allowedOrigins("*").allowedMethods("*").allowedHeaders("*");
	}
}
