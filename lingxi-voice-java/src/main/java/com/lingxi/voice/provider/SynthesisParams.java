package com.lingxi.voice.provider;

public record SynthesisParams(
    double speed,
    double pitch,
    double volume,
    String emotion,
    String style,
    String language,
    String instruction
) {
    public SynthesisParams() { this(1.0, 0.0, 1.0, null, null, "zh", null); }

    public static SynthesisParams from(com.lingxi.voice.dto.TtsRequest req) {
        return new SynthesisParams(
            req.speed(), 0.0, 1.0,
            req.emotion(), req.style(), req.language(), req.instruction()
        );
    }
}
