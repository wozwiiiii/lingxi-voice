package com.lingxi.voice.repository;

import com.lingxi.voice.entity.SynthesisTask;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;

public interface SynthesisTaskRepository extends JpaRepository<SynthesisTask, UUID> {
    List<SynthesisTask> findByUserIdOrderByCreatedAtDesc(UUID userId);
}
