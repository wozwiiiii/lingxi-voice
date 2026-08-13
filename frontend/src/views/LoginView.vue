<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const mode = ref<"login" | "register">("login");
const email = ref("");
const username = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

function switchMode(m: "login" | "register") {
  mode.value = m;
  error.value = "";
}

function extractError(e: any, fallback: string): string {
  const detail = e.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { msg?: string }) => d.msg || "")
      .filter(Boolean)
      .join("；");
  }
  return detail || fallback;
}

async function handleSubmit() {
  if (loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    if (mode.value === "login") {
      await auth.loginUser(email.value, password.value);
    } else {
      await auth.registerUser(email.value, username.value, password.value);
      try {
        await auth.loginUser(email.value, password.value);
      } catch {
        error.value = "注册成功，但自动登录失败，请返回登录";
        mode.value = "login";
        return;
      }
    }
    router.push("/");
  } catch (e: any) {
    error.value = extractError(e, mode.value === "login" ? "登录失败" : "注册失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <a-card class="login-card" :bordered="false">
      <div class="login-header">
        <h1 class="login-title">灵犀语伴</h1>
        <p class="login-subtitle">
          {{ mode === "login" ? "欢迎回来，让教学更有声音" : "创建账号，开启有声教学" }}
        </p>
      </div>

      <a-form @submit.prevent="handleSubmit" layout="vertical">
        <a-form-item v-if="mode === 'register'" label="用户名">
          <a-input v-model:value="username" placeholder="请输入用户名" size="large" />
        </a-form-item>
        <a-form-item label="邮箱">
          <a-input v-model:value="email" type="email" placeholder="请输入邮箱" size="large" />
        </a-form-item>
        <a-form-item label="密码">
          <a-input-password v-model:value="password" placeholder="请输入密码" size="large" />
        </a-form-item>
        <a-button
          type="primary"
          html-type="submit"
          :loading="loading"
          size="large"
          block
        >
          {{ mode === "login" ? "登录" : "注册" }}
        </a-button>
      </a-form>

      <a-alert
        v-if="error"
        type="error"
        :message="error"
        style="margin-top: 16px"
        closable
        @close="error = ''"
      />

      <div class="login-footer">
        <a-button v-if="mode === 'login'" type="link" :disabled="loading" @click="switchMode('register')">
          还没有账号？去注册
        </a-button>
        <a-button v-else type="link" :disabled="loading" @click="switchMode('login')">
          已有账号？去登录
        </a-button>
      </div>
    </a-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e64a19 0%, #d84315 100%);
  padding: 24px;
}
.login-card {
  width: 100%;
  max-width: 400px;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}
.login-header {
  text-align: center;
  margin-bottom: 24px;
}
.login-title {
  font-size: 24px;
  font-weight: 700;
  color: #ff7043;
  margin: 0 0 4px;
}
.login-subtitle {
  color: #757575;
  margin: 0;
}
.login-footer {
  text-align: center;
  margin-top: 16px;
}
</style>
