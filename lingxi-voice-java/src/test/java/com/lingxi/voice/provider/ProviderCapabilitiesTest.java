package com.lingxi.voice.provider;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("ProviderCapabilities")
class ProviderCapabilitiesTest {

    @Test
    @DisplayName("forSiliconFlow should include zh and en languages")
    void siliconFlowIncludesZhAndEn() {
        ProviderCapabilities caps = ProviderCapabilities.forSiliconFlow();
        assertThat(caps.languages()).contains("zh", "en", "ja", "ko");
    }

    @Test
    @DisplayName("forSiliconFlow should support mp3 and wav formats")
    void siliconFlowSupportsMp3Wav() {
        ProviderCapabilities caps = ProviderCapabilities.forSiliconFlow();
        assertThat(caps.supportedFormats()).contains("mp3", "wav");
    }

    @Test
    @DisplayName("forSiliconFlow should have instructMode = false")
    void siliconFlowInstructModeIsFalse() {
        ProviderCapabilities caps = ProviderCapabilities.forSiliconFlow();
        assertThat(caps.instructMode()).isFalse();
    }

    @Test
    @DisplayName("forLocal should have more emotions than forSiliconFlow")
    void localHasMoreEmotions() {
        ProviderCapabilities local = ProviderCapabilities.forLocal();
        ProviderCapabilities cloud = ProviderCapabilities.forSiliconFlow();
        assertThat(local.emotions().size()).isGreaterThan(cloud.emotions().size());
    }

    @Test
    @DisplayName("forLocal should have instructMode = true")
    void localInstructModeIsTrue() {
        ProviderCapabilities caps = ProviderCapabilities.forLocal();
        assertThat(caps.instructMode()).isTrue();
    }

    @Test
    @DisplayName("forLocal should include yue (Cantonese) language")
    void localIncludesCantonese() {
        ProviderCapabilities caps = ProviderCapabilities.forLocal();
        assertThat(caps.languages()).contains("yue");
    }

    @Test
    @DisplayName("forLocal should have non-empty styles list")
    void localHasStyles() {
        ProviderCapabilities caps = ProviderCapabilities.forLocal();
        assertThat(caps.styles()).isNotEmpty();
        assertThat(caps.styles()).contains("新闻播报", "故事讲述", "客服对话", "教学讲解");
    }
}
