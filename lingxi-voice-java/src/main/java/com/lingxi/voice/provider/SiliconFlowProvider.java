package com.lingxi.voice.provider;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import java.util.List;
import java.util.concurrent.CompletableFuture;

@Component
@ConditionalOnProperty(name = "tts.provider", havingValue = "cloud:siliconflow",
                       matchIfMissing = true)
public class SiliconFlowProvider implements TtsProvider {

    private final String apiKey;
    private final String baseUrl;
    private final ProviderCapabilities caps = ProviderCapabilities.forSiliconFlow();

    public SiliconFlowProvider(
        @Value("${tts.siliconflow.api-key}") String apiKey,
        @Value("${tts.siliconflow.base-url}") String baseUrl
    ) {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
    }

    @Override public String name() { return "cloud:siliconflow"; }
    @Override public ProviderCapabilities capabilities() { return caps; }

    @Override
    public CompletableFuture<AudioResult> synthesize(String text, String voiceId,
                                                      SynthesisParams params) {
        return CompletableFuture.supplyAsync(() -> {
            // TODO: integrate with SiliconFlow OpenAI-compatible /audio/speech endpoint
            // For now: stub returning empty audio
            return new AudioResult(new byte[0], "mp3", 0);
        });
    }

    @Override
    public CompletableFuture<byte[]> synthesizeStream(String text, String voiceId,
                                                       SynthesisParams params) {
        return CompletableFuture.completedFuture(new byte[0]);
    }

    @Override
    public CompletableFuture<VoiceMetadata> cloneVoice(byte[] audio, String name) {
        return CompletableFuture.completedFuture(
            new VoiceMetadata("clone_" + System.currentTimeMillis(), name, name(), true)
        );
    }

    @Override
    public CompletableFuture<List<VoiceMetadata>> listPresetVoices() {
        return CompletableFuture.completedFuture(List.of(
            new VoiceMetadata("zh_female_wenrou", "温柔女声", name(), false),
            new VoiceMetadata("zh_male_qingse", "青涩男声", name(), false),
            new VoiceMetadata("zh_male_zhubo", "男主播", name(), false),
            new VoiceMetadata("zh_female_zhubo", "女主播", name(), false),
            new VoiceMetadata("en_male_narrator", "English Male", name(), false),
            new VoiceMetadata("en_female_narrator", "English Female", name(), false)
        ));
    }

    @Override
    public CompletableFuture<Boolean> checkHealth() {
        return CompletableFuture.completedFuture(true);
    }
}
