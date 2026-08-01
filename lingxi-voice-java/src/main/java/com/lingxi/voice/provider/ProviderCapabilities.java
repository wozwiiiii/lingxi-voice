package com.lingxi.voice.provider;

import java.util.List;

public record ProviderCapabilities(
    int maxTextLength,
    List<String> supportedFormats,
    boolean streaming,
    List<String> emotions,
    List<String> styles,
    List<String> languages,
    boolean instructMode,
    boolean zeroShotClone,
    double cloneMinDuration,
    double cloneMaxDuration
) {
    public static ProviderCapabilities forSiliconFlow() {
        return new ProviderCapabilities(
            1000, List.of("mp3", "wav"), true,
            List.of("高兴", "悲伤", "愤怒", "惊讶", "中性", "温柔", "严肃", "活泼"),
            List.of(),
            List.of("zh", "en", "ja", "ko"),
            false, true, 3.0, 30.0
        );
    }

    public static ProviderCapabilities forLocal() {
        return new ProviderCapabilities(
            2000, List.of("wav", "mp3"), true,
            List.of("高兴", "悲伤", "愤怒", "惊讶", "恐惧", "厌恶", "中性",
                    "兴奋", "温柔", "严肃", "活泼", "低沉", "明亮", "急促", "缓慢", "清晰"),
            List.of("新闻播报", "故事讲述", "客服对话", "教学讲解"),
            List.of("zh", "en", "ja", "ko", "yue"),
            true, true, 5.0, 30.0
        );
    }
}
