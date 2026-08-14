import axios from "axios";
import type { InternalAxiosRequestConfig } from "axios";
import router from "../router";

const apiClient = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// --- token 自动续期（single-flight） ---
// 多个请求同时 401 时只发起一次 refresh，其余请求排队等待新 token 后重放。
let isRefreshing = false;
type RetryQueueItem = { config: InternalAxiosRequestConfig; resolve: (val: any) => void };

let retryQueue: RetryQueueItem[] = [];

function flushQueue(token: string) {
  retryQueue.forEach(({ config, resolve }) => {
    config.headers.Authorization = `Bearer ${token}`;
    resolve(apiClient(config));
  });
  retryQueue = [];
}

function clearQueue() {
  retryQueue = [];
}

// 用裸 axios 发 refresh：不经过 apiClient，避免拦截器递归/循环依赖
async function tryRefresh(): Promise<string | null> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) return null;
  try {
    const { data } = await axios.post("/api/auth/refresh", {
      refresh_token: refreshToken,
    });
    localStorage.setItem("access_token", data.access_token);
    if (data.refresh_token) {
      localStorage.setItem("refresh_token", data.refresh_token);
    }
    return data.access_token as string;
  } catch {
    return null;
  }
}

function handleAuthFailure() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  if (window.location.pathname !== "/login") {
    router.push({ name: "login" });
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as InternalAxiosRequestConfig | undefined;
    // 非 401 或刷新请求本身失败：直接透传错误
    if (!error.response || error.response.status !== 401 || !original || original.url?.includes("/auth/")) {
      return Promise.reject(error);
    }
    // 已经重放过一次仍 401：说明 refresh 已失效或 token 彻底过期
    if ((original as any)._retry) {
      handleAuthFailure();
      return Promise.reject(error);
    }

    if (!isRefreshing) {
      isRefreshing = true;
      const newToken = await tryRefresh();
      isRefreshing = false;
      if (newToken) {
        flushQueue(newToken);
        // 当前请求也重放
        original.headers.Authorization = `Bearer ${newToken}`;
        (original as any)._retry = true;
        return apiClient(original);
      } else {
        clearQueue();
        handleAuthFailure();
        return Promise.reject(error);
      }
    }

    // 刷新进行中：挂起当前请求，等新 token 后重放
    return new Promise((resolve) => {
      retryQueue.push({ config: original, resolve });
    });
  }
);

export default apiClient;
