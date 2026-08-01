package com.lingxi.voice.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.*;

@Entity
@Table(name = "voices")
public class Voice {

    public enum VoiceType { preset, cloned }

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User owner;

    @Column(nullable = false, length = 200)
    private String name;

    @Column(length = 500)
    private String description;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private VoiceType type;

    @Column(name = "is_public")
    private boolean isPublic;

    @Column(nullable = false, length = 50)
    private String provider;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "provider_metadata", columnDefinition = "jsonb")
    private Map<String, Object> providerMetadata = new HashMap<>();

    @Column(name = "reference_audio_path", length = 500)
    private String referenceAudioPath;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "consent_id")
    private Consent consent;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private Instant createdAt;

    public Voice() {}

    // Getters and setters
    public UUID getId() { return id; }
    public User getOwner() { return owner; }
    public void setOwner(User owner) { this.owner = owner; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getDescription() { return description; }
    public void setDescription(String desc) { this.description = desc; }
    public VoiceType getType() { return type; }
    public void setType(VoiceType type) { this.type = type; }
    public boolean isPublic() { return isPublic; }
    public void setPublic(boolean isPublic) { this.isPublic = isPublic; }
    public String getProvider() { return provider; }
    public void setProvider(String provider) { this.provider = provider; }
    public Map<String, Object> getProviderMetadata() { return providerMetadata; }
    public void setProviderMetadata(Map<String, Object> meta) { this.providerMetadata = meta; }
    public String getReferenceAudioPath() { return referenceAudioPath; }
    public void setReferenceAudioPath(String path) { this.referenceAudioPath = path; }
    public Consent getConsent() { return consent; }
    public void setConsent(Consent c) { this.consent = c; }
    public Instant getCreatedAt() { return createdAt; }
}
