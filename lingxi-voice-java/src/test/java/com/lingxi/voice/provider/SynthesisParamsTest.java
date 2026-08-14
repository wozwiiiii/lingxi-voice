package com.lingxi.voice.provider;

import com.lingxi.voice.dto.TtsRequest;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("SynthesisParams")
class SynthesisParamsTest {

    @Test
    @DisplayName("default constructor should set reasonable defaults")
    void defaultsAreReasonable() {
        SynthesisParams p = new SynthesisParams();
        assertThat(p.speed()).isEqualTo(1.0);
        assertThat(p.pitch()).isEqualTo(0.0);
        assertThat(p.volume()).isEqualTo(1.0);
        assertThat(p.language()).isEqualTo("zh");
    }

    @Nested
    @DisplayName("from(TtsRequest)")
    class FromTtsRequest {

        @Test
        @DisplayName("should pass speed through as multiplier (1.5 -> 1.5)")
        void passesThroughSpeedMultiplier() {
            TtsRequest req = new TtsRequest("hello", "voice-1", 1.5, null, null, null, null);
            SynthesisParams p = SynthesisParams.from(req);
            assertThat(p.speed()).isEqualTo(1.5);
        }

        @Test
        @DisplayName("should pass through language, emotion, style, instruction")
        void passesThroughOptionalFields() {
            TtsRequest req = new TtsRequest("hello", "voice-1", 1.0,
                "高兴", "新闻播报", "en", "speak slowly",
                "mp3");

            SynthesisParams p = SynthesisParams.from(req);

            assertThat(p.emotion()).isEqualTo("高兴");
            assertThat(p.style()).isEqualTo("新闻播报");
            assertThat(p.language()).isEqualTo("en");
            assertThat(p.instruction()).isEqualTo("speak slowly");
        }
    }
}
