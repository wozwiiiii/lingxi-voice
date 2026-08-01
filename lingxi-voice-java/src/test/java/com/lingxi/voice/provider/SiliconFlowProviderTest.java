package com.lingxi.voice.provider;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("SiliconFlowProvider")
class SiliconFlowProviderTest {

    private SiliconFlowProvider provider;

    @BeforeEach
    void setUp() {
        provider = new SiliconFlowProvider("test-api-key", "https://api.siliconflow.cn/v1");
    }

    @Test
    @DisplayName("should return correct provider name")
    void returnsCorrectName() {
        assertThat(provider.name()).isEqualTo("cloud:siliconflow");
    }

    @Test
    @DisplayName("should return non-null ProviderCapabilities")
    void returnsCapabilities() {
        ProviderCapabilities caps = provider.capabilities();
        assertThat(caps).isNotNull();
        assertThat(caps.maxTextLength()).isPositive();
        assertThat(caps.supportedFormats()).isNotEmpty();
    }

    @Test
    @DisplayName("synthesize should return future with AudioResult")
    void synthesizeReturnsFuture() throws Exception {
        CompletableFuture<TtsProvider.AudioResult> future =
            provider.synthesize("hello", "zh_female_wenrou", new SynthesisParams());

        TtsProvider.AudioResult result = future.get(5, TimeUnit.SECONDS);
        assertThat(result).isNotNull();
        assertThat(result.format()).isEqualTo("mp3");
    }

    @Test
    @DisplayName("synthesizeStream should return future with byte array")
    void synthesizeStreamReturnsFuture() throws Exception {
        CompletableFuture<byte[]> future =
            provider.synthesizeStream("hello", "zh_female_wenrou", new SynthesisParams());

        byte[] result = future.get(5, TimeUnit.SECONDS);
        assertThat(result).isNotNull();
    }

    @Test
    @DisplayName("listPresetVoices should return exactly 6 voices")
    void listPresetVoicesReturnsSix() throws Exception {
        CompletableFuture<List<TtsProvider.VoiceMetadata>> future =
            provider.listPresetVoices();

        List<TtsProvider.VoiceMetadata> voices = future.get(5, TimeUnit.SECONDS);
        assertThat(voices).hasSize(6);
        assertThat(voices).allMatch(v -> v.voiceId() != null && v.name() != null);
    }

    @Test
    @DisplayName("cloneVoice should return a voice metadata with isCloned=true")
    void cloneVoiceReturnsClonedMetadata() throws Exception {
        CompletableFuture<TtsProvider.VoiceMetadata> future =
            provider.cloneVoice(new byte[]{1, 2, 3}, "my-cloned-voice");

        TtsProvider.VoiceMetadata meta = future.get(5, TimeUnit.SECONDS);
        assertThat(meta.isCloned()).isTrue();
        assertThat(meta.name()).isEqualTo("my-cloned-voice");
    }

    @Test
    @DisplayName("checkHealth should return true")
    void checkHealthReturnsTrue() throws Exception {
        CompletableFuture<Boolean> future = provider.checkHealth();

        Boolean healthy = future.get(5, TimeUnit.SECONDS);
        assertThat(healthy).isTrue();
    }
}
