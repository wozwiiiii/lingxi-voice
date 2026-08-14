package com.lingxi.voice.security;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@DisplayName("SecurityConfig (integration)")
class SecurityConfigTest {

    @Autowired private MockMvc mockMvc;

    @Nested
    @DisplayName("Public endpoints (no auth required)")
    class PublicEndpoints {

        @Test
        @DisplayName("GET /api/health should return 200 without authentication")
        void healthIsPublic() throws Exception {
            mockMvc.perform(get("/api/health"))
                .andExpect(status().isOk());
        }

        @Test
        @DisplayName("GET /api/capabilities should return 200 without authentication")
        void capabilitiesIsPublic() throws Exception {
            mockMvc.perform(get("/api/capabilities"))
                .andExpect(status().isOk());
        }

        @Test
        @DisplayName("POST /api/auth/register should be accessible without auth")
        void registerIsPublic() throws Exception {
            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"test@example.com","username":"testuser","password":"password123"}"""))
                .andExpect(status().isCreated());
        }

        @Test
        @DisplayName("POST /api/auth/login should be accessible without auth")
        void loginIsPublic() throws Exception {
            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"login@example.com","username":"loginuser","password":"password123"}"""))
                .andExpect(status().isCreated());

            mockMvc.perform(post("/api/auth/login")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"login@example.com","password":"password123"}"""))
                .andExpect(status().isOk());
        }

        @Test
        @DisplayName("POST /api/auth/refresh should be accessible without auth")
        void refreshIsPublic() throws Exception {
            mockMvc.perform(post("/api/auth/refresh")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"refresh_token":"some-refresh-token"}"""))
                .andExpect(status().isUnauthorized());
        }

        @Test
        @DisplayName("GET /api/voices should be accessible without auth (visitor support)")
        void voicesIsPublic() throws Exception {
            mockMvc.perform(get("/api/voices"))
                .andExpect(status().isOk());
        }

        @Test
        @DisplayName("POST /api/tts/synthesize should be accessible without auth (visitor support)")
        void ttsSynthesizeIsPublic() throws Exception {
            mockMvc.perform(post("/api/tts/synthesize")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"text":"hello","voice_id":"v1","speed":1.0}"""))
                .andExpect(status().isOk());
        }
    }

    @Nested
    @DisplayName("Protected endpoints (auth required)")
    class ProtectedEndpoints {

        @Test
        @DisplayName("GET /api/courseware/projects should return 401 without auth")
        void coursewareRequiresAuth() throws Exception {
            mockMvc.perform(get("/api/courseware/projects"))
                .andExpect(status().isUnauthorized());
        }
    }
}
