package com.lingxi.voice.service;

import com.lingxi.voice.dto.*;
import com.lingxi.voice.entity.User;
import com.lingxi.voice.repository.UserRepository;
import com.lingxi.voice.security.JwtTokenProvider;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
@org.springframework.transaction.annotation.Transactional
public class AuthService {
    private final UserRepository userRepo;
    private final PasswordEncoder encoder;
    private final JwtTokenProvider jwt;

    public AuthService(UserRepository repo, PasswordEncoder enc, JwtTokenProvider jwt) {
        this.userRepo = repo; this.encoder = enc; this.jwt = jwt;
    }

    public UserResponse register(RegisterRequest req) {
        if (userRepo.existsByEmailOrUsername(req.email(), req.username())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                "Registration failed. If you already have an account, please log in.");
        }
        var user = new User(req.email(), req.username(), encoder.encode(req.password()));
        user = userRepo.save(user);
        return new UserResponse(user.getId().toString(), user.getEmail(),
                                user.getUsername(), user.getRole());
    }

    public TokenResponse login(LoginRequest req) {
        var user = userRepo.findByEmail(req.email())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED,
                "Invalid credentials"));
        if (!encoder.matches(req.password(), user.getPasswordHash())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials");
        }
        String access = jwt.createAccessToken(user.getId());
        String refresh = jwt.createRefreshToken(user.getId());
        return new TokenResponse(access, refresh);
    }
}
