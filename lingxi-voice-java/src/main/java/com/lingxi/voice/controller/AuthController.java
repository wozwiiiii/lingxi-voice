package com.lingxi.voice.controller;

import com.lingxi.voice.dto.*;
import com.lingxi.voice.repository.UserRepository;
import com.lingxi.voice.service.AuthService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.userdetails.User;
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

    @GetMapping("/me")
    public ResponseEntity<UserResponse> me(@AuthenticationPrincipal User principal) {
        if (principal == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        return userRepo.findById(UUID.fromString(principal.getUsername()))
            .map(u -> ResponseEntity.ok(
                new UserResponse(u.getId().toString(), u.getEmail(), u.getUsername(), u.getRole())))
            .orElse(ResponseEntity.status(HttpStatus.NOT_FOUND).build());
    }
}
