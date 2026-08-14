package com.lingxi.voice.controller;

import com.lingxi.voice.dto.LoginRequest;
import com.lingxi.voice.dto.RegisterRequest;
import com.lingxi.voice.dto.TokenResponse;
import com.lingxi.voice.dto.UserResponse;
import com.lingxi.voice.repository.UserRepository;
import com.lingxi.voice.security.JwtTokenProvider;
import com.lingxi.voice.service.AuthService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithAnonymousUser;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(AuthController.class)
@AutoConfigureMockMvc(addFilters = false)
@DisplayName("AuthController")
class AuthControllerTest {

    @Autowired private MockMvc mockMvc;
    @MockBean private AuthService authService;
    @MockBean private JwtTokenProvider jwtTokenProvider;
    @MockBean private UserRepository userRepo;

    @Nested
    @DisplayName("POST /api/auth/register")
    class RegisterEndpoint {

        @Test
        @DisplayName("should return 201 with user data on valid registration")
        @WithAnonymousUser
        void returns201OnValidRegistration() throws Exception {
            RegisterRequest req = new RegisterRequest("test@example.com", "testuser", "password123");
            when(authService.register(any(RegisterRequest.class)))
                .thenReturn(new UserResponse("uuid-1", "test@example.com", "testuser", "user"));

            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"test@example.com","username":"testuser","password":"password123"}"""))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.email").value("test@example.com"))
                .andExpect(jsonPath("$.username").value("testuser"))
                .andExpect(jsonPath("$.role").value("user"));
        }

        @Test
        @DisplayName("should return 400 for missing email")
        @WithAnonymousUser
        void returns400ForMissingEmail() throws Exception {
            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"username":"testuser","password":"password123"}"""))
                .andExpect(status().isBadRequest());
        }

        @Test
        @DisplayName("should return 400 for short password")
        @WithAnonymousUser
        void returns400ForShortPassword() throws Exception {
            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"test@example.com","username":"testuser","password":"123"}"""))
                .andExpect(status().isBadRequest());
        }

        @Test
        @DisplayName("should return 400 for invalid email format")
        @WithAnonymousUser
        void returns400ForInvalidEmail() throws Exception {
            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"not-an-email","username":"testuser","password":"password123"}"""))
                .andExpect(status().isBadRequest());
        }
    }

    @Nested
    @DisplayName("POST /api/auth/login")
    class LoginEndpoint {

        @Test
        @DisplayName("should return 200 with tokens on valid login")
        @WithAnonymousUser
        void returns200OnValidLogin() throws Exception {
            when(authService.login(any(LoginRequest.class)))
                .thenReturn(new TokenResponse("access-xxx", "refresh-xxx"));

            mockMvc.perform(post("/api/auth/login")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"test@example.com","password":"password123"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.access_token").value("access-xxx"))
                .andExpect(jsonPath("$.refresh_token").value("refresh-xxx"))
                .andExpect(jsonPath("$.token_type").value("bearer"));
        }

        @Test
        @DisplayName("should return 400 for blank password")
        @WithAnonymousUser
        void returns400ForBlankPassword() throws Exception {
            mockMvc.perform(post("/api/auth/login")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"test@example.com","password":""}"""))
                .andExpect(status().isBadRequest());
        }
    }

    @Nested
    @DisplayName("GET /api/auth/me")
    class MeEndpoint {

        @Test
        @DisplayName("should return 401 for anonymous request (no principal)")
        @WithAnonymousUser
        void returns401ForAnonymous() throws Exception {
            mockMvc.perform(get("/api/auth/me"))
                .andExpect(status().isUnauthorized());
        }
        // The authenticated happy path (String principal -> profile) is covered end-to-end by
        // AuthIntegrationTest.FullAuthFlow.registerLoginAccessFlow, which drives the real
        // JwtAuthenticationFilter + AuthController.
    }

    @Nested
    @DisplayName("POST /api/auth/refresh")
    class RefreshEndpoint {

        @Test
        @DisplayName("should return a fresh token pair for a valid refresh token")
        @WithAnonymousUser
        void returnsTokensOnValidRefresh() throws Exception {
            when(authService.refreshAccess("refresh-xxx"))
                .thenReturn(new TokenResponse("new-access-xxx", "new-refresh-xxx"));

            mockMvc.perform(post("/api/auth/refresh")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"refresh_token":"refresh-xxx"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.access_token").value("new-access-xxx"))
                .andExpect(jsonPath("$.refresh_token").value("new-refresh-xxx"))
                .andExpect(jsonPath("$.token_type").value("bearer"));
        }

        @Test
        @DisplayName("should return 400 for blank refresh token")
        @WithAnonymousUser
        void returns400ForBlankRefreshToken() throws Exception {
            mockMvc.perform(post("/api/auth/refresh")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"refresh_token":""}"""))
                .andExpect(status().isBadRequest());
        }
    }

    @Nested
    @DisplayName("POST /api/auth/logout")
    class LogoutEndpoint {

        @Test
        @DisplayName("should return 204 for a valid Bearer access token")
        @WithAnonymousUser
        void returns204WithBearerToken() throws Exception {
            mockMvc.perform(post("/api/auth/logout")
                    .header("Authorization", "Bearer access-token"))
                .andExpect(status().isNoContent());
        }

        @Test
        @DisplayName("should return 204 even without an Authorization header")
        @WithAnonymousUser
        void returns204WithoutHeader() throws Exception {
            mockMvc.perform(post("/api/auth/logout"))
                .andExpect(status().isNoContent());
        }
    }
}
