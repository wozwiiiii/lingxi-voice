package com.lingxi.voice.dto;

public record UserResponse(
    String id,
    String email,
    String username,
    String role
) {}
