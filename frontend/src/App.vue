<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import AppLayout from "./components/AppLayout.vue";
import { themeConfig } from "./theme";
import { useAuthStore } from "./stores/auth";

const route = useRoute();
const auth = useAuthStore();
// 登录/注册页全屏独立，不套用导航布局
const isAuthPage = computed(() => route.name === "login");

// 应用启动时恢复登录状态（仅当本地存在 token 时，避免未登录用户触发 401 跳转）
onMounted(() => {
  if (localStorage.getItem("access_token")) {
    auth.fetchUser();
  }
});
</script>

<template>
  <a-config-provider :theme="themeConfig">
    <router-view v-if="isAuthPage" />
    <AppLayout v-else>
      <router-view />
    </AppLayout>
  </a-config-provider>
</template>
