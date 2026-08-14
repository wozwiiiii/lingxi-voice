package com.lingxi.voice.integration;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@DisplayName("Auth Integration Test")
class AuthIntegrationTest {

    @Autowired private MockMvc mockMvc;

    @Nested
    @DisplayName("Full registration -> login -> authenticated access flow")
    class FullAuthFlow {

        @Test
        @DisplayName("should register, login, and access protected endpoint")
        void registerLoginAccessFlow() throws Exception {
            // Step 1: Register
            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"flow@example.com","username":"flowuser","password":"password123"}"""))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.email").value("flow@example.com"));

            // Step 2: Login
            MvcResult loginResult = mockMvc.perform(post("/api/auth/login")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"flow@example.com","password":"password123"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.access_token").exists())
                .andExpect(jsonPath("$.refresh_token").exists())
                .andExpect(jsonPath("$.token_type").value("bearer"))
                .andReturn();

            String accessToken = com.jayway.jsonpath.JsonPath
                .read(loginResult.getResponse().getContentAsString(), "$.access_token");

            // Step 3: Fetch profile with JWT
            mockMvc.perform(get("/api/auth/me")
                    .header("Authorization", "Bearer " + accessToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value("flow@example.com"))
                .andExpect(jsonPath("$.username").value("flowuser"));
        }

        @Test
        @DisplayName("should refresh tokens with a valid refresh token")
        void refreshesTokens() throws Exception {
            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"refresh@example.com","username":"refreshuser","password":"password123"}"""))
                .andExpect(status().isCreated());

            MvcResult loginResult = mockMvc.perform(post("/api/auth/login")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"refresh@example.com","password":"password123"}"""))
                .andExpect(status().isOk())
                .andReturn();

            String refreshToken = com.jayway.jsonpath.JsonPath
                .read(loginResult.getResponse().getContentAsString(), "$.refresh_token");

            mockMvc.perform(post("/api/auth/refresh")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("{\"refresh_token\":\"" + refreshToken + "\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.access_token").exists())
                .andExpect(jsonPath("$.refresh_token").exists())
                .andExpect(jsonPath("$.token_type").value("bearer"));
        }

        @Test
        @DisplayName("should reject refresh with a bogus token (401)")
        void rejectsBogusRefresh() throws Exception {
            mockMvc.perform(post("/api/auth/refresh")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"refresh_token":"not-a-real-token"}"""))
                .andExpect(status().isUnauthorized());
        }

        @Test
        @DisplayName("should return 204 on logout with a valid access token")
        void logoutReturns204() throws Exception {
            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"logout@example.com","username":"logoutuser","password":"password123"}"""))
                .andExpect(status().isCreated());

            MvcResult loginResult = mockMvc.perform(post("/api/auth/login")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"logout@example.com","password":"password123"}"""))
                .andExpect(status().isOk())
                .andReturn();

            String accessToken = com.jayway.jsonpath.JsonPath
                .read(loginResult.getResponse().getContentAsString(), "$.access_token");

            mockMvc.perform(post("/api/auth/logout")
                    .header("Authorization", "Bearer " + accessToken))
                .andExpect(status().isNoContent());
        }

        @Test
        @DisplayName("should reject duplicate registration with 409")
        void rejectsDuplicateRegistration() throws Exception {
            // First registration
            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"dup-flow@example.com","username":"dupflow","password":"password123"}"""))
                .andExpect(status().isCreated());

            // Second registration with same email
            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"dup-flow@example.com","username":"othername","password":"password123"}"""))
                .andExpect(status().isConflict());
        }

        @Test
        @DisplayName("should reject login with wrong password")
        void rejectsWrongPassword() throws Exception {
            mockMvc.perform(post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"wrongpw@example.com","username":"wrongpw","password":"password123"}"""))
                .andExpect(status().isCreated());

            mockMvc.perform(post("/api/auth/login")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"email":"wrongpw@example.com","password":"WRONG_PASSWORD"}"""))
                .andExpect(status().isUnauthorized());
        }
    }

    @Nested
    @DisplayName("Security boundary tests")
    class SecurityBoundaries {

        @Test
        @DisplayName("should reject protected endpoint without Authorization header")
        void rejectsProtectedEndpointWithoutAuth() throws Exception {
            mockMvc.perform(get("/api/courseware/projects"))
                .andExpect(status().isUnauthorized());
        }

        @Test
        @DisplayName("should reject protected endpoint with malformed token")
        void rejectsMalformedToken() throws Exception {
            mockMvc.perform(get("/api/courseware/projects")
                    .header("Authorization", "Bearer not-a-real-jwt"))
                .andExpect(status().isUnauthorized());
        }

        @Test
        @DisplayName("should allow anonymous access to /api/voices")
        void voicesIsPublic() throws Exception {
            mockMvc.perform(get("/api/voices"))
                .andExpect(status().isOk());
        }

        @Test
        @DisplayName("should allow anonymous access to /api/tts/synthesize")
        void ttsIsPublic() throws Exception {
            mockMvc.perform(post("/api/tts/synthesize")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("""
                        {"text":"hello","voice_id":"v1","speed":1.0}"""))
                .andExpect(status().isOk());
        }
    }
}
