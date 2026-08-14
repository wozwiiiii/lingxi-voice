package com.lingxi.voice.dto;

import jakarta.validation.constraints.*;

public record LoginRequest(
    @NotBlank @Email String email,
    @NotBlank @Size(min = 8, max = 128) String password
) {}
