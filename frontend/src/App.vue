<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import AppLayout from "./components/AppLayout.vue";
import { themeConfig } from "./theme";

const route = useRoute();
// 登录/注册页全屏独立，不套用导航布局
const isAuthPage = computed(() => route.name === "login");
</script>

<template>
  <a-config-provider :theme="themeConfig">
    <router-view v-if="isAuthPage" />
    <AppLayout v-else>
      <router-view />
    </AppLayout>
  </a-config-provider>
</template>
