package com.lingxi.voice.dto;

public record TtsResponse(
    String taskId,
    String status,
    String audioUrl,
    boolean cached,
    String providerUsed,
    Integer durationMs,
    String processedText
) {}
