package com.lingxi.voice.security;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.Refill;
import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.Duration;
import java.util.concurrent.TimeUnit;

// NOTE: do NOT add @Component here — it is registered manually in AppConfig
// to avoid double-invocation from component scan + FilterRegistrationBean.
public class RateLimitFilter implements Filter {
    private final Cache<String, Bucket> buckets = Caffeine.newBuilder()
        .expireAfterAccess(5, TimeUnit.MINUTES)
        .maximumSize(10_000)
        .build();

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) req;
        HttpServletResponse response = (HttpServletResponse) res;

        String path = request.getRequestURI();
        if (!path.startsWith("/api/") || path.startsWith("/api/health")) {
            chain.doFilter(req, res);
            return;
        }

        String key = request.getRemoteAddr();
        Bucket bucket = buckets.get(key, k ->
            Bucket.builder()
                .addLimit(Bandwidth.classic(30,
                    Refill.greedy(30, Duration.ofMinutes(1))))
                .build()
        );

        if (bucket.tryConsume(1)) {
            chain.doFilter(req, res);
        } else {
            response.setStatus(429);
            response.setHeader("Retry-After", "60");
            response.setContentType("application/json");
            response.getWriter().write(
                "{\"error\":{\"code\":\"RATE_LIMITED\",\"message\":\"请求过于频繁，请稍后重试\"}}"
            );
        }
    }
}
