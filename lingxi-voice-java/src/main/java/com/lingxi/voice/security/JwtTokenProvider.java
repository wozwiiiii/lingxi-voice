package com.lingxi.voice.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;

@Component
public class JwtTokenProvider {
    private final SecretKey key;
    private final long accessExpiration;
    private final long refreshExpiration;

    public JwtTokenProvider(
        @Value("${jwt.secret}") String secret,
        @Value("${jwt.access-token-expiration}") String accessExp,
        @Value("${jwt.refresh-token-expiration}") String refreshExp
    ) {
        if (secret == null || secret.isBlank() || secret.length() < 32) {
            throw new IllegalArgumentException(
                "JWT secret must be at least 32 characters. Set JWT_SECRET_KEY environment variable."
            );
        }
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.accessExpiration = parseDuration(accessExp);
        this.refreshExpiration = parseDuration(refreshExp);
    }

    public String createAccessToken(UUID userId) {
        Instant now = Instant.now();
        return Jwts.builder()
            .subject(userId.toString())
            .id(UUID.randomUUID().toString())
            .claim("type", "access")
            .issuedAt(Date.from(now))
            .expiration(Date.from(now.plusMillis(accessExpiration)))
            .signWith(key)
            .compact();
    }

    public String createRefreshToken(UUID userId) {
        Instant now = Instant.now();
        return Jwts.builder()
            .subject(userId.toString())
            .id(UUID.randomUUID().toString())
            .claim("type", "refresh")
            .issuedAt(Date.from(now))
            .expiration(Date.from(now.plusMillis(refreshExpiration)))
            .signWith(key)
            .compact();
    }

    public Claims validateToken(String token) {
        return Jwts.parser().verifyWith(key).build()
            .parseSignedClaims(token).getPayload();
    }

    private long parseDuration(String s) {
        if (s.endsWith("m")) return Long.parseLong(s.replace("m", "")) * 60000;
        if (s.endsWith("h")) return Long.parseLong(s.replace("h", "")) * 3600000;
        if (s.endsWith("d")) return Long.parseLong(s.replace("d", "")) * 86400000;
        throw new IllegalArgumentException(
            "Invalid duration: '" + s + "'. Use format: 30m, 2h, 7d"
        );
    }
}
