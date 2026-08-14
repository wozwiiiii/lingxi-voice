package com.lingxi.voice.controller;

import com.lingxi.voice.dto.*;
import com.lingxi.voice.repository.UserRepository;
import com.lingxi.voice.service.AuthService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private final AuthService authService;
    private final UserRepository userRepo;

    public AuthController(AuthService svc, UserRepository userRepo) {
        this.authService = svc;
        this.userRepo = userRepo;
    }

    @PostMapping("/register")
    public ResponseEntity<UserResponse> register(@Valid @RequestBody RegisterRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(authService.register(req));
    }

    @PostMapping("/login")
    public ResponseEntity<TokenResponse> login(@Valid @RequestBody LoginRequest req) {
        return ResponseEntity.ok(authService.login(req));
    }

    @PostMapping("/refresh")
    public ResponseEntity<TokenResponse> refresh(@Valid @RequestBody RefreshRequest req) {
        return ResponseEntity.ok(authService.refreshAccess(req.refreshToken()));
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(
            @RequestHeader(value = "Authorization", required = false) String authHeader) {
        // Contract: endpoint MUST exist and return 204 so the frontend logout flow does not
        // get a 404. Production should blacklist the access token's jti here — the Java version
        // has no blacklist infrastructure yet, so this is intentionally a no-op returning 204.
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/me")
    public ResponseEntity<UserResponse> me(@AuthenticationPrincipal Object principal) {
        // JwtAuthenticationFilter sets the principal to the token subject (a UUID string).
        // Anonymous/anonymous-with-invalid-subject must yield 401, not 400/404.
        if (!(principal instanceof String userId)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        UUID id;
        try {
            id = UUID.fromString(userId);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        return userRepo.findById(id)
            .map(u -> ResponseEntity.ok(
                new UserResponse(u.getId().toString(), u.getEmail(), u.getUsername(), u.getRole())))
            .orElse(ResponseEntity.status(HttpStatus.NOT_FOUND).build());
    }
}
