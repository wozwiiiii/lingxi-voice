package com.lingxi.voice.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("JwtAuthenticationFilter")
class JwtAuthenticationFilterTest {

    private static final String SECRET = "test-secret-key-that-is-at-least-32-characters-long!!";

    @Mock private HttpServletRequest request;
    @Mock private HttpServletResponse response;
    @Mock private FilterChain chain;

    private JwtTokenProvider jwtProvider;
    private JwtAuthenticationFilter filter;

    @BeforeEach
    void setUp() {
        jwtProvider = new JwtTokenProvider(SECRET, "30m", "7d");
        filter = new JwtAuthenticationFilter(jwtProvider);
        SecurityContextHolder.clearContext();
    }

    @Nested
    @DisplayName("doFilterInternal")
    class DoFilterInternal {

        @Test
        @DisplayName("should set authentication context for valid access token")
        void setsAuthForValidAccessToken() throws Exception {
            String token = jwtProvider.createAccessToken(UUID.randomUUID());
            when(request.getHeader("Authorization")).thenReturn("Bearer " + token);

            filter.doFilterInternal(request, response, chain);

            Authentication auth = SecurityContextHolder.getContext().getAuthentication();
            assertThat(auth).isNotNull();
            assertThat(auth.getPrincipal()).isNotNull();
        }

        @Test
        @DisplayName("should NOT set authentication for a refresh token (type != access)")
        void rejectsRefreshTokenForAuth() throws Exception {
            String token = jwtProvider.createRefreshToken(UUID.randomUUID());
            when(request.getHeader("Authorization")).thenReturn("Bearer " + token);

            filter.doFilterInternal(request, response, chain);

            Authentication auth = SecurityContextHolder.getContext().getAuthentication();
            assertThat(auth).isNull();
        }

        @Test
        @DisplayName("should NOT set authentication when Authorization header is missing")
        void skipsWhenNoHeader() throws Exception {
            when(request.getHeader("Authorization")).thenReturn(null);

            filter.doFilterInternal(request, response, chain);

            Authentication auth = SecurityContextHolder.getContext().getAuthentication();
            assertThat(auth).isNull();
            verify(chain).doFilter(request, response);
        }

        @Test
        @DisplayName("should NOT set authentication when header does not start with Bearer")
        void skipsNonBearerHeader() throws Exception {
            when(request.getHeader("Authorization")).thenReturn("Basic YWRtaW46cGFzcw==");

            filter.doFilterInternal(request, response, chain);

            Authentication auth = SecurityContextHolder.getContext().getAuthentication();
            assertThat(auth).isNull();
            verify(chain).doFilter(request, response);
        }

        @Test
        @DisplayName("should proceed without auth when token is invalid (JwtException)")
        void skipsInvalidToken() throws Exception {
            when(request.getHeader("Authorization")).thenReturn("Bearer invalid.token.here");

            filter.doFilterInternal(request, response, chain);

            Authentication auth = SecurityContextHolder.getContext().getAuthentication();
            assertThat(auth).isNull();
            verify(chain).doFilter(request, response);
        }

        @Test
        @DisplayName("should always call the next filter in chain regardless of token validity")
        void alwaysContinuesChain() throws Exception {
            // No header
            when(request.getHeader("Authorization")).thenReturn(null);
            filter.doFilterInternal(request, response, chain);
            verify(chain, times(1)).doFilter(request, response);

            // Invalid token
            when(request.getHeader("Authorization")).thenReturn("Bearer garbage");
            filter.doFilterInternal(request, response, chain);
            verify(chain, times(2)).doFilter(request, response);

            // Valid token
            String token = jwtProvider.createAccessToken(UUID.randomUUID());
            when(request.getHeader("Authorization")).thenReturn("Bearer " + token);
            filter.doFilterInternal(request, response, chain);
            verify(chain, times(3)).doFilter(request, response);
        }
    }
}
