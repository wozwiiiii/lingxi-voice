package com.lingxi.voice.config;

import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

import com.lingxi.voice.security.RateLimitFilter;

@Configuration
public class AppConfig {

    @Bean
    public FilterRegistrationBean<RateLimitFilter> rateLimitFilterReg(RateLimitFilter filter) {
        var reg = new FilterRegistrationBean<>(filter);
        reg.addUrlPatterns("/api/*");
        reg.setOrder(1);
        return reg;
    }

    @Bean
    public RestClient restClient() {
        return RestClient.create();
    }
}
