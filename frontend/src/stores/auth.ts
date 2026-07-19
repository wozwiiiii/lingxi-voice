import { defineStore } from "pinia";
import { ref } from "vue";
import { login as apiLogin, register as apiRegister, getMe } from "../api/auth";
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

  function logout() {
    user.value = null;
    isAuthenticated.value = false;
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  return { user, isAuthenticated, loginUser, registerUser, fetchUser, logout };
});
