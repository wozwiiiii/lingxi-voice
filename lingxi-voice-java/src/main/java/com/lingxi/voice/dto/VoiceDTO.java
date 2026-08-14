package com.lingxi.voice.dto;

public record VoiceDTO(
    String id,
    String name,
    String type,
    String provider,
    boolean isPublic,
    String description
) {}
