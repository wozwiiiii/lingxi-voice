package com.lingxi.voice.dto;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class ValidationTest {

    private Validator validator;

    @BeforeEach
    void setUp() {
        ValidatorFactory factory = Validation.buildDefaultValidatorFactory();
        validator = factory.getValidator();
    }

    @Test
    void shouldRejectBlankEmail() {
        RegisterRequest req = new RegisterRequest("", "user123", "password123");
        Set<ConstraintViolation<RegisterRequest>> violations = validator.validate(req);
        assertThat(violations).isNotEmpty();
    }

    @Test
    void shouldRejectInvalidEmail() {
        RegisterRequest req = new RegisterRequest("not-an-email", "user123", "password123");
        Set<ConstraintViolation<RegisterRequest>> violations = validator.validate(req);
        assertThat(violations).isNotEmpty();
    }

    @Test
    void shouldRejectShortUsername() {
        RegisterRequest req = new RegisterRequest("a@b.com", "ab", "password123");
        Set<ConstraintViolation<RegisterRequest>> violations = validator.validate(req);
        assertThat(violations).isNotEmpty();
    }

    @Test
    void shouldRejectShortPassword() {
        RegisterRequest req = new RegisterRequest("a@b.com", "user123", "123");
        Set<ConstraintViolation<RegisterRequest>> violations = validator.validate(req);
        assertThat(violations).isNotEmpty();
    }

    @Test
    void shouldAcceptValidRegisterRequest() {
        RegisterRequest req = new RegisterRequest("valid@test.com", "validuser", "password123");
        Set<ConstraintViolation<RegisterRequest>> violations = validator.validate(req);
        assertThat(violations).isEmpty();
    }

    @Test
    void shouldRejectBlankTtsText() {
        TtsRequest req = new TtsRequest("", "voice_id", 100, null, null, "zh", null);
        Set<ConstraintViolation<TtsRequest>> violations = validator.validate(req);
        assertThat(violations).isNotEmpty();
    }

    @Test
    void shouldRejectOversizedText() {
        String huge = "x".repeat(2001);
        TtsRequest req = new TtsRequest(huge, "voice_id", 100, null, null, "zh", null);
        Set<ConstraintViolation<TtsRequest>> violations = validator.validate(req);
        assertThat(violations).isNotEmpty();
    }

    @Test
    void shouldAcceptValidTtsRequest() {
        TtsRequest req = new TtsRequest("测试文本", "voice_id", 100, null, null, "zh", null);
        Set<ConstraintViolation<TtsRequest>> violations = validator.validate(req);
        assertThat(violations).isEmpty();
    }
}
