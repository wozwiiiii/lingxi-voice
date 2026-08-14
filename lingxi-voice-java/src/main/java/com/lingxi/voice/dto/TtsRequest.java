package com.lingxi.voice.dto;

import jakarta.validation.constraints.*;

public record TtsRequest(
    @NotBlank @Size(max = 2000) String text,
    @NotBlank String voiceId,
    @DecimalMin(value = "0.5", message = "speed must be between 0.5 and 3.0")
    @DecimalMax(value = "3.0", message = "speed must be between 0.5 and 3.0")
    double speed,
    String emotion,
    String style,
    String language,
    @Size(max = 200) String instruction,
    String outputFormat
) {
    public TtsRequest(String text, String voiceId, double speed,
                      String emotion, String style, String language, String instruction) {
        this(text, voiceId, speed, emotion, style, language, instruction, "wav");
    }
}
