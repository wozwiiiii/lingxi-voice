package com.lingxi.voice.config;

import dev.langchain4j.model.openai.OpenAiChatModel;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class AiConfig {

    @Bean
    public OpenAiChatModel chatModel(
        @Value("${langchain4j.openai.api-key}") String apiKey,
        @Value("${langchain4j.openai.base-url}") String baseUrl
    ) {
        return OpenAiChatModel.builder()
            .apiKey(apiKey)
            .baseUrl(baseUrl)
            .modelName("deepseek-chat")
            .temperature(0.1)
            .build();
    }
}
