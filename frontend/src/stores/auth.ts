import { defineStore } from "pinia";
import { ref } from "vue";
import { login as apiLogin, register as apiRegister, getMe, logout as apiLogout } from "../api/auth";
import type { UserInfo } from "../types";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<UserInfo | null>(null);
  const isAuthenticated = ref(false);

  async function loginUser(email: string, password: string) {
    const tokens = await apiLogin(email, password);
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    await fetchUser();
  }

  async function registerUser(email: string, username: string, password: string) {
    await apiRegister(email, username, password);
  }

  async function fetchUser() {
    try {
      user.value = await getMe();
      isAuthenticated.value = true;
    } catch {
      logout();
    }
  }

  async function logout() {
    // 通知后端拉黑 refresh token（fire-and-forget：本地登出不等待，失败也不阻塞）
    const refreshToken = localStorage.getItem("refresh_token") || undefined;
    try {
      await apiLogout(refreshToken);
    } catch { /* 本地登出始终生效 */ }
    user.value = null;
    isAuthenticated.value = false;
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  return { user, isAuthenticated, loginUser, registerUser, fetchUser, logout };
});
