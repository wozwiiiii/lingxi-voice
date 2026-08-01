package com.lingxi.voice.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.*;

@Entity
@Table(name = "synthesis_tasks")
public class SynthesisTask {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "voice_id", nullable = false)
    private Voice voice;

    @Column(nullable = false, length = 20)
    private String type;

    @Column(name = "input_text", columnDefinition = "TEXT")
    private String inputText;

    @Column(name = "llm_processed_text", columnDefinition = "TEXT")
    private String llmProcessedText;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private Map<String, Object> params = new HashMap<>();

    @Column(nullable = false, length = 20)
    private String status = "pending";

    @Column(name = "output_audio_path", length = 500)
    private String outputAudioPath;

    @Column(name = "output_format", length = 10)
    private String outputFormat = "wav";

    @Column(name = "celery_task_id", length = 100)
    private String celeryTaskId;

    @Column(nullable = false)
    private int progress;

    @Column(name = "error_code", length = 50)
    private String errorCode;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(nullable = false)
    private boolean cached;

    @Column(name = "provider_used", length = 50)
    private String providerUsed;

    @Column(name = "duration_ms")
    private Integer durationMs;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private Instant createdAt;

    public SynthesisTask() {}

    public UUID getId() { return id; }
    public void setUser(User u) { this.user = u; }
    public void setVoice(Voice v) { this.voice = v; }
    public void setType(String t) { this.type = t; }
    public void setInputText(String t) { this.inputText = t; }
    public void setLlmProcessedText(String t) { this.llmProcessedText = t; }
    public void setParams(Map<String, Object> p) { this.params = p; }
    public void setStatus(String s) { this.status = s; }
    public void setOutputAudioPath(String p) { this.outputAudioPath = p; }
    public void setOutputFormat(String f) { this.outputFormat = f; }
    public void setCached(boolean c) { this.cached = c; }
    public void setProviderUsed(String p) { this.providerUsed = p; }
    public void setDurationMs(Integer ms) { this.durationMs = ms; }
    // Use getOutputAudioPath() instead — a second getter would confuse JPA property mapping
    public String getInputText() { return inputText; }
    public String getOutputAudioPath() { return outputAudioPath; }
}
