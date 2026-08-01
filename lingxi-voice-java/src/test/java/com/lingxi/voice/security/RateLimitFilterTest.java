package com.lingxi.voice.security;

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

import java.io.PrintWriter;
import java.io.StringWriter;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("RateLimitFilter")
class RateLimitFilterTest {

    @Mock private HttpServletRequest request;
    @Mock private HttpServletResponse response;
    @Mock private FilterChain chain;

    private RateLimitFilter filter;

    @BeforeEach
    void setUp() {
        filter = new RateLimitFilter();
    }

    @Nested
    @DisplayName("doFilter")
    class DoFilter {

        @Test
        @DisplayName("should bypass rate limiting for non-/api/ paths")
        void bypassesNonApiPaths() throws Exception {
            when(request.getRequestURI()).thenReturn("/static/style.css");

            filter.doFilter(request, response, chain);

            verify(chain).doFilter(request, response);
            verify(response, never()).setStatus(anyInt());
        }

        @Test
        @DisplayName("should bypass rate limiting for /api/health")
        void bypassesHealthEndpoint() throws Exception {
            when(request.getRequestURI()).thenReturn("/api/health");

            filter.doFilter(request, response, chain);

            verify(chain).doFilter(request, response);
            verify(response, never()).setStatus(anyInt());
        }

        @Test
        @DisplayName("should allow request when under rate limit")
        void allowsUnderLimit() throws Exception {
            when(request.getRequestURI()).thenReturn("/api/tts/synthesize");
            when(request.getRemoteAddr()).thenReturn("192.168.1.1");

            filter.doFilter(request, response, chain);

            verify(chain).doFilter(request, response);
            verify(response, never()).setStatus(eq(429));
        }

        @Test
        @DisplayName("should return 429 when rate limit exceeded")
        void blocksWhenExceeded() throws Exception {
            when(request.getRequestURI()).thenReturn("/api/tts/synthesize");
            when(request.getRemoteAddr()).thenReturn("192.168.1.2");

            StringWriter sw = new StringWriter();
            when(response.getWriter()).thenReturn(new PrintWriter(sw));

            // Exhaust the bucket (30 requests per minute)
            for (int i = 0; i < 31; i++) {
                filter.doFilter(request, response, chain);
            }

            verify(response, atLeastOnce()).setStatus(429);
            assertThat(sw.toString()).contains("RATE_LIMITED");
        }

        @Test
        @DisplayName("should set Retry-After header on 429 response")
        void setsRetryAfterHeader() throws Exception {
            when(request.getRequestURI()).thenReturn("/api/tts/synthesize");
            when(request.getRemoteAddr()).thenReturn("192.168.1.3");

            StringWriter sw = new StringWriter();
            when(response.getWriter()).thenReturn(new PrintWriter(sw));

            for (int i = 0; i < 31; i++) {
                filter.doFilter(request, response, chain);
            }

            verify(response, atLeastOnce()).setHeader("Retry-After", "60");
        }

        @Test
        @DisplayName("should rate-limit each IP address independently")
        void isolatesByIp() throws Exception {
            HttpServletRequest req1 = mock(HttpServletRequest.class);
            HttpServletRequest req2 = mock(HttpServletRequest.class);
            HttpServletResponse res1 = mock(HttpServletResponse.class);
            HttpServletResponse res2 = mock(HttpServletResponse.class);
            FilterChain chain1 = mock(FilterChain.class);
            FilterChain chain2 = mock(FilterChain.class);

            when(req1.getRequestURI()).thenReturn("/api/tts/synthesize");
            when(req1.getRemoteAddr()).thenReturn("10.0.0.1");
            when(req2.getRequestURI()).thenReturn("/api/tts/synthesize");
            when(req2.getRemoteAddr()).thenReturn("10.0.0.2");

            // Exhaust IP 10.0.0.1's bucket
            for (int i = 0; i < 31; i++) {
                filter.doFilter(req1, res1, chain1);
            }
            verify(res1, atLeastOnce()).setStatus(429);

            // IP 10.0.0.2 should still be allowed
            filter.doFilter(req2, res2, chain2);
            verify(chain2).doFilter(req2, res2);
            verify(res2, never()).setStatus(429);
        }

        @Test
        @DisplayName("should return JSON content type on 429")
        void returnsJsonContentType() throws Exception {
            when(request.getRequestURI()).thenReturn("/api/tts/synthesize");
            when(request.getRemoteAddr()).thenReturn("192.168.1.4");

            StringWriter sw = new StringWriter();
            when(response.getWriter()).thenReturn(new PrintWriter(sw));

            for (int i = 0; i < 31; i++) {
                filter.doFilter(request, response, chain);
            }

            verify(response, atLeastOnce()).setContentType("application/json");
        }
    }
}
