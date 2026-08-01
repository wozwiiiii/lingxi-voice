package com.lingxi.voice.dto;

import jakarta.validation.constraints.*;

public record TtsRequest(
    @NotBlank @Size(max = 2000) String text,
    @NotBlank String voiceId,
    @Min(50) @Max(300) int speed,
    String emotion,
    String style,
    String language,
    @Size(max = 200) String instruction,
    String outputFormat
) {
    public TtsRequest(String text, String voiceId, int speed,
                      String emotion, String style, String language, String instruction) {
        this(text, voiceId, speed, emotion, style, language, instruction, "wav");
    }
}

public record TtsResponse(
    String taskId,
    String status,
    String audioUrl,
    boolean cached,
    String providerUsed,
    Integer durationMs,
    String processedText
) {}

public record VoiceDTO(
    String id,
    String name,
    String type,
    String provider,
    boolean isPublic,
    String description
) {}
