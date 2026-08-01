package com.lingxi.voice.provider;

import com.lingxi.voice.dto.TtsRequest;
import java.util.List;
import java.util.concurrent.CompletableFuture;

public interface TtsProvider {
    String name();
    ProviderCapabilities capabilities();
    CompletableFuture<AudioResult> synthesize(String text, String voiceId, SynthesisParams params);
    CompletableFuture<byte[]> synthesizeStream(String text, String voiceId, SynthesisParams params);
    CompletableFuture<VoiceMetadata> cloneVoice(byte[] audio, String name);
    CompletableFuture<List<VoiceMetadata>> listPresetVoices();
    CompletableFuture<Boolean> checkHealth();

    record AudioResult(byte[] audioData, String format, int durationMs) {}
    record VoiceMetadata(String voiceId, String name, String provider, boolean isCloned) {}
}
