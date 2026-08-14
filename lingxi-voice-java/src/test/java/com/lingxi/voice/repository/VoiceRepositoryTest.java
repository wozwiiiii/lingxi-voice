package com.lingxi.voice.repository;

import com.lingxi.voice.entity.User;
import com.lingxi.voice.entity.Voice;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class VoiceRepositoryTest {

    @Autowired
    private TestEntityManager em;

    @Autowired
    private VoiceRepository voiceRepo;

    @Autowired
    private UserRepository userRepo;

    private User owner;

    @BeforeEach
    void setUp() {
        owner = new User("test@example.com", "testuser", "hashed");
        em.persist(owner);
    }

    @Test
    void shouldFindPresetVoices() {
        var voice = createVoice("测试预设", Voice.VoiceType.preset, true, null);
        em.persist(voice);
        em.flush();

        List<Voice> presets = voiceRepo.findByIsPublicTrueOrderByCreatedAt();
        assertThat(presets).hasSize(1);
        assertThat(presets.get(0).getName()).isEqualTo("测试预设");
    }

    @Test
    void shouldNotReturnPrivateVoicesInPresetQuery() {
        var cloned = createVoice("我的克隆", Voice.VoiceType.cloned, false, owner);
        em.persist(cloned);
        em.flush();

        List<Voice> presets = voiceRepo.findByIsPublicTrueOrderByCreatedAt();
        assertThat(presets).isEmpty();
    }

    @Test
    void shouldFindVoicesByOwner() {
        var cloned = createVoice("我的声音", Voice.VoiceType.cloned, false, owner);
        em.persist(cloned);
        em.flush();

        List<Voice> myVoices = voiceRepo.findByOwnerIdOrderByCreatedAtDesc(owner.getId());
        assertThat(myVoices).hasSize(1);
        assertThat(myVoices.get(0).getOwner().getId()).isEqualTo(owner.getId());
    }

    @Test
    void shouldDetectDuplicateName() {
        var v1 = createVoice("unique_name", Voice.VoiceType.cloned, false, owner);
        em.persist(v1);
        em.flush();

        boolean exists = voiceRepo.existsByOwnerIdAndName(owner.getId(), "unique_name");
        assertThat(exists).isTrue();

        boolean notExists = voiceRepo.existsByOwnerIdAndName(owner.getId(), "nonexistent");
        assertThat(notExists).isFalse();
    }

    private Voice createVoice(String name, Voice.VoiceType type, boolean isPublic, User owner) {
        var v = new Voice();
        v.setName(name);
        v.setType(type);
        v.setPublic(isPublic);
        v.setProvider("cloud:siliconflow");
        if (owner != null) v.setOwner(owner);
        return v;
    }
}
