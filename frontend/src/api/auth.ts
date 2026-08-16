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

export async function logout(refreshToken?: string): Promise<void> {
  // 携带 refresh_token 以便后端登出时一并拉黑（否则泄露的 refresh token 登出后仍可用）
  await apiClient.post("/auth/logout", refreshToken ? { refresh_token: refreshToken } : {});
}

export async function getMe(): Promise<UserInfo> {
  const { data } = await apiClient.get<UserInfo>("/auth/me");
  return data;
}
