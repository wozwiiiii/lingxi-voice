package com.lingxi.voice.controller;

import com.lingxi.voice.dto.TtsRequest;
import com.lingxi.voice.dto.TtsResponse;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/tts")
public class TtsController {

    @PostMapping("/synthesize")
    public ResponseEntity<TtsResponse> synthesize(@Valid @RequestBody TtsRequest request) {
        // Stub: return placeholder response
        return ResponseEntity.ok(new TtsResponse(
            UUID.randomUUID().toString(), "completed",
            "/media/audio/placeholder.mp3", false,
            "cloud:siliconflow", 0, null
        ));
    }
}
