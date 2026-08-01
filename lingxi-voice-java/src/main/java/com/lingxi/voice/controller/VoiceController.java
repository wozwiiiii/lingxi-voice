package com.lingxi.voice.controller;

import com.lingxi.voice.dto.VoiceDTO;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/voices")
public class VoiceController {

    @GetMapping
    public ResponseEntity<List<VoiceDTO>> list() {
        return ResponseEntity.ok(List.of(
            new VoiceDTO("a0000000-0000-0000-0000-000000000001",
                "温柔女声", "preset", "cloud:siliconflow", true, "温暖柔和的女声"),
            new VoiceDTO("a0000000-0000-0000-0000-000000000005",
                "English Male", "preset", "cloud:siliconflow", true, "Clear English male voice")
        ));
    }
}
