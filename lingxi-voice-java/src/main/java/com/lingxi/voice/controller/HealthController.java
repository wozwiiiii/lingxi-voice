package com.lingxi.voice.controller;

import com.lingxi.voice.provider.TtsProvider;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
public class HealthController {
    private final List<TtsProvider> providers;

    public HealthController(List<TtsProvider> providers) {
        this.providers = providers;
    }

    @GetMapping("/api/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "ok"));
    }

    @GetMapping("/api/capabilities")
    public ResponseEntity<List<Map<String, Object>>> capabilities() {
        return ResponseEntity.ok(providers.stream()
            .map(p -> Map.<String, Object>of(
                "provider", p.name(),
                "capabilities", p.capabilities()
            )).toList());
    }
}
