<script setup lang="ts">
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();

function handleMenuClick({ key }: { key: string }) {
  router.push(key);
}
</script>

<template>
  <a-layout style="min-height: 100vh">
    <a-layout-header style="display: flex; align-items: center; justify-content: space-between">
      <a-space>
        <span style="color: white; font-size: 18px; font-weight: bold">灵犀语伴</span>
        <a-menu mode="horizontal" theme="dark" :selected-keys="[$route.path]" @click="handleMenuClick">
          <a-menu-item key="/">首页</a-menu-item>
          <a-menu-item key="/tts">文本转语音</a-menu-item>
          <a-menu-item key="/courseware">课件库</a-menu-item>
        </a-menu>
      </a-space>
      <a-space>
        <template v-if="auth.isAuthenticated">
          <span style="color: white">{{ auth.user?.username }}</span>
          <a-button type="link" @click="auth.logout()">退出</a-button>
        </template>
        <a-button v-else type="link" @click="router.push('/login')">登录</a-button>
      </a-space>
    </a-layout-header>
    <a-layout-content style="padding: 24px">
      <slot />
    </a-layout-content>
  </a-layout>
</template>
