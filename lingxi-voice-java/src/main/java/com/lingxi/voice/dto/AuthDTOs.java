package com.lingxi.voice.dto;

import jakarta.validation.constraints.*;

public record RegisterRequest(
    @NotBlank @Email String email,
    @NotBlank @Size(min = 3, max = 50) String username,
    @NotBlank @Size(min = 8, max = 128) String password
) {}

public record LoginRequest(
    @NotBlank @Email String email,
    @NotBlank @Size(min = 8, max = 128) String password
) {}

public record TokenResponse(
    String accessToken,
    String refreshToken,
    String tokenType
) {
    public TokenResponse(String access, String refresh) {
        this(access, refresh, "bearer");
    }
}

public record RefreshRequest(
    @NotBlank String refreshToken
) {}

public record UserResponse(
    String id,
    String email,
    String username,
    String role
) {}
