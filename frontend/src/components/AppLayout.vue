<script setup lang="ts">
import { h, ref, computed } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "../stores/auth";
import {
  HomeOutlined,
  SoundOutlined,
  FileTextOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  UserOutlined,
} from "@ant-design/icons-vue";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const collapsed = ref(false);

const menuItems = [
  { key: "/", icon: () => h(HomeOutlined), label: "首页" },
  { key: "/tts", icon: () => h(SoundOutlined), label: "文本转语音" },
  { key: "/courseware", icon: () => h(FileTextOutlined), label: "课件库" },
];

// 让课件库菜单在 /courseware、/courseware/new、/courseware/:id 下都保持高亮
const selectedKeys = computed(() =>
  route.path.startsWith("/courseware") ? ["/courseware"] : [route.path]
);

function handleMenuClick({ key }: { key: string }) {
  router.push(key);
}

function handleLogout() {
  auth.logout();
  router.push("/login");
}

function onBreakpoint(broken: boolean) {
  collapsed.value = broken;
}
</script>

<template>
  <a-layout style="min-height: 100vh">
    <!-- 可收起侧边栏 -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      :trigger="null"
      :width="220"
      theme="light"
      breakpoint="xl"
      @breakpoint="onBreakpoint"
    >
      <div class="logo">
        <span v-if="!collapsed">灵犀语伴</span>
        <span v-else>灵</span>
      </div>
      <a-menu
        theme="light"
        mode="inline"
        :selected-keys="selectedKeys"
        :items="menuItems"
        @click="handleMenuClick"
      />
    </a-layout-sider>

    <a-layout>
      <!-- 顶部栏 -->
      <a-layout-header class="header">
        <a-button type="text" class="trigger" aria-label="收起/展开菜单" @click="collapsed = !collapsed">
          <MenuUnfoldOutlined v-if="collapsed" />
          <MenuFoldOutlined v-else />
        </a-button>

        <div class="header-right">
          <template v-if="auth.isAuthenticated">
            <a-space :size="12">
              <a-avatar :size="32" class="avatar">
                <template #icon><UserOutlined /></template>
              </a-avatar>
              <span class="username">{{ auth.user?.username }}</span>
              <a-button type="text" @click="handleLogout">
                <template #icon><LogoutOutlined /></template>
                退出
              </a-button>
            </a-space>
          </template>
          <a-button v-else type="primary" @click="router.push('/login')">登录</a-button>
        </div>
      </a-layout-header>

      <!-- 内容区 -->
      <a-layout-content class="content">
        <slot />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<style scoped>
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ff7043;
  font-size: 20px;
  font-weight: 700;
  border-bottom: 1px solid #f0f0f0;
  white-space: nowrap;
  overflow: hidden;
}
.header {
  background: #fff;
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  position: sticky;
  top: 0;
  z-index: 10;
}
.trigger {
  font-size: 18px;
}
.header-right {
  display: flex;
  align-items: center;
}
.avatar {
  background: #ff7043;
}
.username {
  font-size: 14px;
  color: #424242;
}
.content {
  padding: 24px;
}
</style>
