package com.lingxi.voice.repository;

import com.lingxi.voice.entity.Voice;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;

public interface VoiceRepository extends JpaRepository<Voice, UUID> {
    List<Voice> findByIsPublicTrueOrderByCreatedAt();
    List<Voice> findByOwnerIdOrderByCreatedAtDesc(UUID ownerId);
    boolean existsByOwnerIdAndName(UUID ownerId, String name);
}
