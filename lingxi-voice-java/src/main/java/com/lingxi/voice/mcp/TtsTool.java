package com.lingxi.voice.mcp;

import com.lingxi.voice.repository.VoiceRepository;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * MCP Tool: exposes TTS and voice listing as AI Agent-callable tools.
 *
 * Python version equivalent: these capabilities are only accessible via REST API.
 * The Java version adds an MCP layer so AI Agents (Claude Desktop, Cursor, custom agents)
 * can drive TTS through natural language.
 *
 * Interview narrative: "Python版是人用的REST API，Java版在此基础上多一层MCP Server——
 * Agent可以调用。这是2026年企业AI升级的实际模式：不是重写老系统，而是给老系统加一层
 * MCP让AI Agent能驱动它。"
 */
@Component
public class TtsTool {

    private final VoiceRepository voiceRepo;

    public TtsTool(VoiceRepository voiceRepo) {
        this.voiceRepo = voiceRepo;
    }

    /**
     * Lists all available preset voices.
     * Marked as @Tool in production with Spring AI MCP SDK.
     */
    public List<String> listVoices() {
        return voiceRepo.findByIsPublicTrueOrderByCreatedAt().stream()
            .map(v -> v.getId() + ": " + v.getName() +
                      " (" + v.getType() + ", " + v.getProvider() + ")")
            .toList();
    }

    /**
     * Synthesizes text to speech.
     * Marked as @Tool in production with Spring AI MCP SDK.
     */
    public String synthesize(String text, String voiceId, int speed) {
        // In production: delegates to TtsService.synthesize()
        return String.format(
            "Tool: tts_synthesize called with text='%s...', voiceId=%s, speed=%d",
            text.substring(0, Math.min(50, text.length())),
            voiceId, speed
        );
    }
}
