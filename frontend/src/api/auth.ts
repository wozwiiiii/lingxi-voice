import apiClient from "./client";
import type { TokenResponse, UserInfo } from "../types";

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/login", { email, password });
  return data;
}

export async function register(email: string, username: string, password: string) {
  const { data } = await apiClient.post("/auth/register", { email, username, password });
  return data;
}

export async function refresh(refreshToken: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}

export async function getMe(): Promise<UserInfo> {
  const { data } = await apiClient.get<UserInfo>("/auth/me");
  return data;
}
