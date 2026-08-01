package com.lingxi.voice.repository;

import com.lingxi.voice.entity.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@DisplayName("UserRepository")
class UserRepositoryTest {

    @Autowired private UserRepository userRepo;
    @Autowired private TestEntityManager em;

    @Nested
    @DisplayName("findByEmail")
    class FindByEmail {

        @Test
        @DisplayName("should find user by email")
        void findsByEmail() {
            User user = new User("find@example.com", "finder", "hash");
            em.persistAndFlush(user);

            Optional<User> found = userRepo.findByEmail("find@example.com");

            assertThat(found).isPresent();
            assertThat(found.get().getUsername()).isEqualTo("finder");
        }

        @Test
        @DisplayName("should return empty Optional when email not found")
        void returnsEmptyForUnknownEmail() {
            Optional<User> found = userRepo.findByEmail("nobody@example.com");
            assertThat(found).isEmpty();
        }
    }

    @Nested
    @DisplayName("existsByEmailOrUsername")
    class ExistsByEmailOrUsername {

        @Test
        @DisplayName("should return true for existing email")
        void existsByEmail() {
            User user = new User("dup@example.com", "unique-user", "hash");
            em.persistAndFlush(user);

            boolean exists = userRepo.existsByEmailOrUsername("dup@example.com", "other");
            assertThat(exists).isTrue();
        }

        @Test
        @DisplayName("should return true for existing username")
        void existsByUsername() {
            User user = new User("other@example.com", "dup-user", "hash");
            em.persistAndFlush(user);

            boolean exists = userRepo.existsByEmailOrUsername("x@example.com", "dup-user");
            assertThat(exists).isTrue();
        }

        @Test
        @DisplayName("should return false when neither email nor username match")
        void returnsFalseWhenNoMatch() {
            boolean exists = userRepo.existsByEmailOrUsername("none@example.com", "nobody");
            assertThat(exists).isFalse();
        }
    }

    @Nested
    @DisplayName("save")
    class Save {

        @Test
        @DisplayName("should persist user and assign UUID")
        void persistsUserWithUuid() {
            User user = new User("save@example.com", "saver", "hash");
            User saved = userRepo.save(user);

            assertThat(saved.getId()).isNotNull();
            assertThat(saved.getCreatedAt()).isNotNull();
        }
    }
}
