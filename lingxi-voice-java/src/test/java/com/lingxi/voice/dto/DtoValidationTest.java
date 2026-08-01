package com.lingxi.voice.dto;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("DTO Bean Validation")
class DtoValidationTest {

    private static Validator validator;

    @BeforeAll
    static void setUpValidator() {
        ValidatorFactory factory = Validation.buildDefaultValidatorFactory();
        validator = factory.getValidator();
    }

    @Nested
    @DisplayName("RegisterRequest")
    class RegisterRequestValidation {

        @Test
        @DisplayName("should pass with valid data")
        void validDataPasses() {
            RegisterRequest req = new RegisterRequest("a@b.com", "username", "password123");
            Set<ConstraintViolation<RegisterRequest>> violations = validator.validate(req);
            assertThat(violations).isEmpty();
        }

        @Test
        @DisplayName("should reject blank email")
        void rejectsBlankEmail() {
            RegisterRequest req = new RegisterRequest("", "username", "password123");
            assertThat(validator.validate(req)).isNotEmpty();
        }

        @Test
        @DisplayName("should reject invalid email format")
        void rejectsInvalidEmail() {
            RegisterRequest req = new RegisterRequest("not-email", "username", "password123");
            Set<ConstraintViolation<RegisterRequest>> violations = validator.validate(req);
            assertThat(violations).anyMatch(v -> v.getPropertyPath().toString().equals("email"));
        }

        @Test
        @DisplayName("should reject short username (less than 3 chars)")
        void rejectsShortUsername() {
            RegisterRequest req = new RegisterRequest("a@b.com", "ab", "password123");
            assertThat(validator.validate(req)).isNotEmpty();
        }

        @Test
        @DisplayName("should reject short password (less than 8 chars)")
        void rejectsShortPassword() {
            RegisterRequest req = new RegisterRequest("a@b.com", "username", "1234567");
            Set<ConstraintViolation<RegisterRequest>> violations = validator.validate(req);
            assertThat(violations).anyMatch(v -> v.getPropertyPath().toString().equals("password"));
        }

        @Test
        @DisplayName("should reject blank username")
        void rejectsBlankUsername() {
            RegisterRequest req = new RegisterRequest("a@b.com", "", "password123");
            assertThat(validator.validate(req)).isNotEmpty();
        }
    }

    @Nested
    @DisplayName("LoginRequest")
    class LoginRequestValidation {

        @Test
        @DisplayName("should pass with valid data")
        void validDataPasses() {
            LoginRequest req = new LoginRequest("a@b.com", "password");
            Set<ConstraintViolation<LoginRequest>> violations = validator.validate(req);
            assertThat(violations).isEmpty();
        }

        @Test
        @DisplayName("should reject blank email")
        void rejectsBlankEmail() {
            LoginRequest req = new LoginRequest("", "password");
            assertThat(validator.validate(req)).isNotEmpty();
        }

        @Test
        @DisplayName("should reject blank password")
        void rejectsBlankPassword() {
            LoginRequest req = new LoginRequest("a@b.com", "   ");
            assertThat(validator.validate(req)).isNotEmpty();
        }

        @Test
        @DisplayName("IMPORTANT: does NOT enforce minimum password length on login")
        void doesNotEnforceMinPasswordLength() {
            // LoginRequest has @NotBlank but no @Size — this documents the current behavior.
            // A password of length 1 with @NotBlank passes validation.
            LoginRequest req = new LoginRequest("a@b.com", "1");
            Set<ConstraintViolation<LoginRequest>> violations = validator.validate(req);
            assertThat(violations).isEmpty();
        }
    }

    @Nested
    @DisplayName("TtsRequest")
    class TtsRequestValidation {

        @Test
        @DisplayName("should pass with valid data")
        void validDataPasses() {
            TtsRequest req = new TtsRequest("hello", "v1", 100, null, null, null, null);
            Set<ConstraintViolation<TtsRequest>> violations = validator.validate(req);
            assertThat(violations).isEmpty();
        }

        @Test
        @DisplayName("should reject blank text")
        void rejectsBlankText() {
            TtsRequest req = new TtsRequest("  ", "v1", 100, null, null, null, null);
            assertThat(validator.validate(req)).isNotEmpty();
        }

        @Test
        @DisplayName("should reject text exceeding 2000 characters")
        void rejectsTooLongText() {
            String longText = "a".repeat(2001);
            TtsRequest req = new TtsRequest(longText, "v1", 100, null, null, null, null);
            assertThat(validator.validate(req)).isNotEmpty();
        }

        @Test
        @DisplayName("should reject speed below 50")
        void rejectsSpeedBelow50() {
            TtsRequest req = new TtsRequest("hello", "v1", 49, null, null, null, null);
            Set<ConstraintViolation<TtsRequest>> violations = validator.validate(req);
            assertThat(violations).anyMatch(v -> v.getPropertyPath().toString().equals("speed"));
        }

        @Test
        @DisplayName("should reject speed above 300")
        void rejectsSpeedAbove300() {
            TtsRequest req = new TtsRequest("hello", "v1", 301, null, null, null, null);
            Set<ConstraintViolation<TtsRequest>> violations = validator.validate(req);
            assertThat(violations).anyMatch(v -> v.getPropertyPath().toString().equals("speed"));
        }

        @Test
        @DisplayName("should reject blank voiceId")
        void rejectsBlankVoiceId() {
            TtsRequest req = new TtsRequest("hello", "", 100, null, null, null, null);
            assertThat(validator.validate(req)).isNotEmpty();
        }
    }

    @Nested
    @DisplayName("RefreshRequest")
    class RefreshRequestValidation {

        @Test
        @DisplayName("should reject blank refresh token")
        void rejectsBlankRefreshToken() {
            RefreshRequest req = new RefreshRequest("");
            assertThat(validator.validate(req)).isNotEmpty();
        }
    }
}
