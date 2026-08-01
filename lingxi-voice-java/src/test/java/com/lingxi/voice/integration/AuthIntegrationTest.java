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
                .andExpect(jsonPath("$.accessToken").exists())
                .andExpect(jsonPath("$.refreshToken").exists())
                .andExpect(jsonPath("$.tokenType").value("bearer"))
                .andReturn();

            String accessToken = com.jayway.jsonpath.JsonPath
                .read(loginResult.getResponse().getContentAsString(), "$.accessToken");

            // Step 3: Access protected endpoint with JWT
            mockMvc.perform(get("/api/voices")
                    .header("Authorization", "Bearer " + accessToken))
                .andExpect(status().isOk());
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
            mockMvc.perform(get("/api/voices"))
                .andExpect(status().isUnauthorized());
        }

        @Test
        @DisplayName("should reject protected endpoint with malformed token")
        void rejectsMalformedToken() throws Exception {
            mockMvc.perform(get("/api/voices")
                    .header("Authorization", "Bearer not-a-real-jwt"))
                .andExpect(status().isUnauthorized());
        }
    }
}
