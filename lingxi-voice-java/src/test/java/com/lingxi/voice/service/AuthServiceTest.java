package com.lingxi.voice.service;

import com.lingxi.voice.dto.LoginRequest;
import com.lingxi.voice.dto.RegisterRequest;
import com.lingxi.voice.dto.TokenResponse;
import com.lingxi.voice.dto.UserResponse;
import com.lingxi.voice.entity.User;
import com.lingxi.voice.repository.UserRepository;
import com.lingxi.voice.security.JwtTokenProvider;
import io.jsonwebtoken.Claims;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.server.ResponseStatusException;

import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("AuthService")
class AuthServiceTest {

    @Mock private UserRepository userRepo;
    @Mock private JwtTokenProvider jwt;

    private PasswordEncoder encoder;
    private AuthService authService;

    @BeforeEach
    void setUp() {
        encoder = new BCryptPasswordEncoder();
        authService = new AuthService(userRepo, encoder, jwt);
    }

    /** User has no public id setter; set the id reflectively for mock return values. */
    private static void setId(User user, UUID id) {
        try {
            var field = User.class.getDeclaredField("id");
            field.setAccessible(true);
            field.set(user, id);
        } catch (ReflectiveOperationException e) {
            throw new RuntimeException(e);
        }
    }

    @Nested
    @DisplayName("register")
    class Register {

        @Test
        @DisplayName("should register a new user with hashed password")
        void registersNewUser() {
            RegisterRequest req = new RegisterRequest("test@example.com", "testuser", "password123");
            when(userRepo.existsByEmailOrUsername(req.email(), req.username())).thenReturn(false);
            User savedUser = new User(req.email(), req.username(), encoder.encode(req.password()));
            setId(savedUser, UUID.fromString("00000000-0000-0000-0000-000000000001"));
            when(userRepo.save(any(User.class))).thenReturn(savedUser);

            UserResponse response = authService.register(req);

            assertThat(response.email()).isEqualTo("test@example.com");
            assertThat(response.username()).isEqualTo("testuser");
            assertThat(response.role()).isEqualTo("user");
            verify(userRepo).save(any(User.class));
        }

        @Test
        @DisplayName("should hash password before saving (plaintext not stored)")
        void hashesPasswordBeforeSaving() {
            RegisterRequest req = new RegisterRequest("test@example.com", "testuser", "password123");
            when(userRepo.existsByEmailOrUsername(req.email(), req.username())).thenReturn(false);
            when(userRepo.save(any(User.class))).thenAnswer(inv -> {
                User u = inv.getArgument(0);
                User saved = new User(u.getEmail(), u.getUsername(), u.getPasswordHash());
                setId(saved, UUID.fromString("00000000-0000-0000-0000-000000000002"));
                return saved;
            });

            authService.register(req);

            verify(userRepo).save(argThat(user ->
                !user.getPasswordHash().equals("password123")
            ));
        }

        @Test
        @DisplayName("should reject duplicate email/username with 409 CONFLICT")
        void rejectsDuplicateEmail() {
            RegisterRequest req = new RegisterRequest("existing@example.com", "existing", "password123");
            when(userRepo.existsByEmailOrUsername(req.email(), req.username())).thenReturn(true);

            assertThatThrownBy(() -> authService.register(req))
                .isInstanceOf(ResponseStatusException.class)
                .extracting("status").isEqualTo(HttpStatus.CONFLICT);

            verify(userRepo, never()).save(any());
        }
    }

    @Nested
    @DisplayName("login")
    class Login {

        @Test
        @DisplayName("should return access and refresh tokens for valid credentials")
        void loginWithValidCredentials() {
            String rawPassword = "password123";
            User user = new User("test@example.com", "testuser", encoder.encode(rawPassword));
            when(userRepo.findByEmail("test@example.com")).thenReturn(Optional.of(user));
            when(jwt.createAccessToken(user.getId())).thenReturn("access-token");
            when(jwt.createRefreshToken(user.getId())).thenReturn("refresh-token");

            TokenResponse response = authService.login(
                new LoginRequest("test@example.com", rawPassword));

            assertThat(response.accessToken()).isEqualTo("access-token");
            assertThat(response.refreshToken()).isEqualTo("refresh-token");
            assertThat(response.tokenType()).isEqualTo("bearer");
        }

        @Test
        @DisplayName("should reject login with wrong password (401 UNAUTHORIZED)")
        void rejectsWrongPassword() {
            User user = new User("test@example.com", "testuser", encoder.encode("correctPassword"));
            when(userRepo.findByEmail("test@example.com")).thenReturn(Optional.of(user));

            assertThatThrownBy(() ->
                authService.login(new LoginRequest("test@example.com", "wrongPassword"))
            )
                .isInstanceOf(ResponseStatusException.class)
                .extracting("status").isEqualTo(HttpStatus.UNAUTHORIZED);
        }

        @Test
        @DisplayName("should reject login for non-existent email (401 UNAUTHORIZED)")
        void rejectsNonExistentEmail() {
            when(userRepo.findByEmail("unknown@example.com")).thenReturn(Optional.empty());

            assertThatThrownBy(() ->
                authService.login(new LoginRequest("unknown@example.com", "password123"))
            )
                .isInstanceOf(ResponseStatusException.class)
                .extracting("status").isEqualTo(HttpStatus.UNAUTHORIZED);
        }

        @Test
        @DisplayName("should use same error message for wrong email and wrong password")
        void sameErrorMessageForWrongEmailAndPassword() {
            when(userRepo.findByEmail("unknown@example.com")).thenReturn(Optional.empty());

            Throwable emailError = catchThrowable(() ->
                authService.login(new LoginRequest("unknown@example.com", "password123")));

            User user = new User("test@example.com", "testuser", encoder.encode("correct"));
            when(userRepo.findByEmail("test@example.com")).thenReturn(Optional.of(user));

            Throwable passwordError = catchThrowable(() ->
                authService.login(new LoginRequest("test@example.com", "wrong")));

            assertThat(emailError).isInstanceOf(ResponseStatusException.class);
            assertThat(passwordError).isInstanceOf(ResponseStatusException.class);
            assertThat(((ResponseStatusException) emailError).getReason())
                .isEqualTo(((ResponseStatusException) passwordError).getReason());
        }
    }

    @Nested
    @DisplayName("refreshAccess")
    class Refresh {

        @Test
        @DisplayName("should issue a fresh token pair for a valid refresh token")
        void issuesFreshTokens() {
            String userId = "00000000-0000-0000-0000-000000000001";
            User user = new User("test@example.com", "testuser", encoder.encode("password123"));
            Claims claims = mock(Claims.class);
            when(jwt.validateToken("refresh-token")).thenReturn(claims);
            when(claims.get("type")).thenReturn("refresh");
            when(claims.getSubject()).thenReturn(userId);
            when(userRepo.findById(UUID.fromString(userId))).thenReturn(Optional.of(user));
            when(jwt.createAccessToken(user.getId())).thenReturn("new-access");
            when(jwt.createRefreshToken(user.getId())).thenReturn("new-refresh");

            TokenResponse response = authService.refreshAccess("refresh-token");

            assertThat(response.accessToken()).isEqualTo("new-access");
            assertThat(response.refreshToken()).isEqualTo("new-refresh");
            assertThat(response.tokenType()).isEqualTo("bearer");
        }

        @Test
        @DisplayName("should reject an access token used as a refresh token (401)")
        void rejectsAccessToken() {
            Claims claims = mock(Claims.class);
            when(jwt.validateToken("access-token")).thenReturn(claims);
            when(claims.get("type")).thenReturn("access");

            assertThatThrownBy(() -> authService.refreshAccess("access-token"))
                .isInstanceOf(ResponseStatusException.class)
                .extracting("status").isEqualTo(HttpStatus.UNAUTHORIZED);

            verify(userRepo, never()).findById(any());
        }

        @Test
        @DisplayName("should reject a refresh token for an unknown user (401)")
        void rejectsUnknownUser() {
            String userId = "00000000-0000-0000-0000-000000000099";
            Claims claims = mock(Claims.class);
            when(jwt.validateToken("refresh-token")).thenReturn(claims);
            when(claims.get("type")).thenReturn("refresh");
            when(claims.getSubject()).thenReturn(userId);
            when(userRepo.findById(UUID.fromString(userId))).thenReturn(Optional.empty());

            assertThatThrownBy(() -> authService.refreshAccess("refresh-token"))
                .isInstanceOf(ResponseStatusException.class)
                .extracting("status").isEqualTo(HttpStatus.UNAUTHORIZED);

            verify(jwt, never()).createAccessToken(any());
        }
    }
}
