package com.lingxi.voice.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.assertj.core.api.Assertions.*;

@DisplayName("JwtTokenProvider")
class JwtTokenProviderTest {

    private static final String SECRET = "test-secret-key-that-is-at-least-32-characters-long!!";
    private JwtTokenProvider provider;

    @BeforeEach
    void setUp() {
        provider = new JwtTokenProvider(SECRET, "30m", "7d");
    }

    @Nested
    @DisplayName("createAccessToken")
    class CreateAccessToken {

        @Test
        @DisplayName("should create a non-null, non-empty token string")
        void createsNonNullToken() {
            String token = provider.createAccessToken(UUID.randomUUID());
            assertThat(token).isNotBlank();
        }

        @Test
        @DisplayName("should embed subject (userId) and type=access in claims")
        void embedsCorrectClaims() {
            UUID userId = UUID.randomUUID();
            String token = provider.createAccessToken(userId);

            Claims claims = provider.validateToken(token);
            assertThat(claims.getSubject()).isEqualTo(userId.toString());
            assertThat(claims.get("type")).isEqualTo("access");
        }

        @Test
        @DisplayName("should have an expiration in the future")
        void expirationIsFuture() {
            String token = provider.createAccessToken(UUID.randomUUID());
            Claims claims = provider.validateToken(token);
            assertThat(claims.getExpiration().toInstant())
                .isAfter(java.time.Instant.now());
        }
    }

    @Nested
    @DisplayName("createRefreshToken")
    class CreateRefreshToken {

        @Test
        @DisplayName("should embed type=refresh in claims")
        void embedsRefreshType() {
            UUID userId = UUID.randomUUID();
            String token = provider.createRefreshToken(userId);

            Claims claims = provider.validateToken(token);
            assertThat(claims.get("type")).isEqualTo("refresh");
        }
    }

    @Nested
    @DisplayName("validateToken")
    class ValidateToken {

        @Test
        @DisplayName("should validate a correctly signed token")
        void validatesCorrectToken() {
            String token = provider.createAccessToken(UUID.randomUUID());
            assertThatCode(() -> provider.validateToken(token))
                .doesNotThrowAnyException();
        }

        @Test
        @DisplayName("should throw JwtException for a token signed with a different key")
        void rejectsWrongKey() {
            JwtTokenProvider otherProvider =
                new JwtTokenProvider("another-secret-key-that-is-different-32chars", "30m", "7d");
            String token = otherProvider.createAccessToken(UUID.randomUUID());

            assertThatThrownBy(() -> provider.validateToken(token))
                .isInstanceOf(JwtException.class);
        }

        @Test
        @DisplayName("should throw JwtException for a garbled token string")
        void rejectsGarbledToken() {
            assertThatThrownBy(() -> provider.validateToken("not.a.jwt.token"))
                .isInstanceOf(JwtException.class);
        }

        @Test
        @DisplayName("should throw JwtException for an empty string")
        void rejectsEmptyString() {
            assertThatThrownBy(() -> provider.validateToken(""))
                .isInstanceOf(JwtException.class);
        }

        @Test
        @DisplayName("should throw ExpiredJwtException for an expired token")
        void rejectsExpiredToken() {
            JwtTokenProvider zeroExpProvider =
                new JwtTokenProvider(SECRET, "0m", "0m");

            assertThatThrownBy(() -> {
                String token = zeroExpProvider.createAccessToken(UUID.randomUUID());
                zeroExpProvider.validateToken(token);
            }).isInstanceOf(ExpiredJwtException.class);
        }
    }

    @Nested
    @DisplayName("parseDuration")
    class ParseDuration {

        @Test
        @DisplayName("should parse minutes correctly")
        void parsesMinutes() {
            JwtTokenProvider p = new JwtTokenProvider(SECRET, "5m", "1d");
            String token = p.createAccessToken(UUID.randomUUID());
            Claims claims = p.validateToken(token);
            long diff = claims.getExpiration().getTime() - claims.getIssuedAt().getTime();
            assertThat(diff).isEqualTo(5 * 60 * 1000L);
        }

        @Test
        @DisplayName("should parse hours correctly")
        void parsesHours() {
            JwtTokenProvider p = new JwtTokenProvider(SECRET, "2h", "1d");
            String token = p.createAccessToken(UUID.randomUUID());
            Claims claims = p.validateToken(token);
            long diff = claims.getExpiration().getTime() - claims.getIssuedAt().getTime();
            assertThat(diff).isEqualTo(2 * 3600 * 1000L);
        }

        @Test
        @DisplayName("should parse days correctly")
        void parsesDays() {
            JwtTokenProvider p = new JwtTokenProvider(SECRET, "1d", "30d");
            String token = p.createAccessToken(UUID.randomUUID());
            Claims claims = p.validateToken(token);
            long diff = claims.getExpiration().getTime() - claims.getIssuedAt().getTime();
            assertThat(diff).isEqualTo(86400 * 1000L);
        }
    }
}
