package com.lingxi.voice.entity;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "consents")
public class Consent {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "audio_sha256", nullable = false, length = 64)
    private String audioSha256;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String purpose;

    @Column(name = "agreed_at", nullable = false)
    private Instant agreedAt;

    @Column(name = "expires_at")
    private Instant expiresAt;

    @Column(name = "revoked_at")
    private Instant revokedAt;

    public Consent() {}

    public UUID getId() { return id; }
    public User getUser() { return user; }
    public void setUser(User u) { this.user = u; }
    public String getAudioSha256() { return audioSha256; }
    public void setAudioSha256(String h) { this.audioSha256 = h; }
    public String getPurpose() { return purpose; }
    public void setPurpose(String p) { this.purpose = p; }
    public Instant getAgreedAt() { return agreedAt; }
    public void setAgreedAt(Instant t) { this.agreedAt = t; }
    public Instant getExpiresAt() { return expiresAt; }
    public void setExpiresAt(Instant t) { this.expiresAt = t; }
    public Instant getRevokedAt() { return revokedAt; }
    public void setRevokedAt(Instant t) { this.revokedAt = t; }
}
