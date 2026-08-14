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
      <!-- 品牌 Logo：渐变圆角方块「灵」字标 + 文字组合 -->
      <div class="logo">
        <div class="logo-mark" aria-hidden="true">灵</div>
        <span v-if="!collapsed" class="logo-text">灵犀语伴</span>
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
      <!-- 顶部栏：毛玻璃 + 细边框 -->
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

      <!-- 内容区：max-width 1280px 居中，大屏不再无限拉伸 -->
      <a-layout-content class="content">
        <div class="content-inner">
          <slot />
        </div>
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
  gap: 10px;
  border-bottom: 1px solid var(--lx-border);
  white-space: nowrap;
  overflow: hidden;
}
.logo-mark {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 10px;
  background: var(--lx-gradient-brand);
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(255, 107, 53, 0.28);
}
.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--lx-text);
}
.header {
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 10;
  /* 毛玻璃效果：半透明底 + 背景模糊 + 细边框（替代生硬阴影） */
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--lx-border);
}
.trigger {
  font-size: 18px;
  color: var(--lx-text-secondary);
}
.header-right {
  display: flex;
  align-items: center;
}
.avatar {
  background: var(--lx-gradient-brand);
}
.username {
  font-size: 14px;
  color: var(--lx-text);
}
.content {
  padding: 24px;
}
.content-inner {
  max-width: 1280px;
  margin: 0 auto;
  width: 100%;
}
</style>
