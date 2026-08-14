package com.lingxi.voice.dto;

public record TokenResponse(
    String accessToken,
    String refreshToken,
    String tokenType
) {
    public TokenResponse(String access, String refresh) {
        this(access, refresh, "bearer");
    }
}
