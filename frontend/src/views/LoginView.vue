<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const email = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

async function handleLogin() {
  loading.value = true;
  error.value = "";
  try {
    await auth.loginUser(email.value, password.value);
    router.push("/");
  } catch (e: any) {
    error.value = e.response?.data?.detail || "登录失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <a-card title="登录" style="max-width: 400px; margin: 40px auto">
    <a-form @submit.prevent="handleLogin">
      <a-form-item label="邮箱">
        <a-input v-model:value="email" type="email" />
      </a-form-item>
      <a-form-item label="密码">
        <a-input-password v-model:value="password" />
      </a-form-item>
      <a-button type="primary" html-type="submit" :loading="loading" block>登录</a-button>
      <a-alert v-if="error" type="error" :message="error" style="margin-top: 12px" closable />
    </a-form>
  </a-card>
</template>
