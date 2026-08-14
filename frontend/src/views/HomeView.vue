<script setup lang="ts">
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import {
  SoundOutlined,
  FileTextOutlined,
  BookOutlined,
} from "@ant-design/icons-vue";

const router = useRouter();
const auth = useAuthStore();

const features = [
  {
    title: "文本转语音",
    desc: "输入文本，一键生成自然流畅的语音，支持多语言多情感",
    icon: SoundOutlined,
    path: "/tts",
  },
  {
    title: "课件合成",
    desc: "上传 PPTX 课件，批量生成有声课件，让教学更生动",
    icon: FileTextOutlined,
    path: "/courseware/new",
  },
  {
    title: "课件库",
    desc: "管理你的课件，复用官方示例，随时编辑与下载",
    icon: BookOutlined,
    path: "/courseware",
  },
];
</script>

<template>
  <div class="fade-up">
    <!-- 欢迎区域：三段渐变 + 装饰圆，层次感更强 -->
    <div class="hero">
      <div class="hero-deco hero-deco-1" aria-hidden="true"></div>
      <div class="hero-deco hero-deco-2" aria-hidden="true"></div>
      <div class="hero-content">
        <h1 class="hero-title">
          {{ auth.isAuthenticated ? `您好，${auth.user?.username}！` : "欢迎来到灵犀语伴" }}
        </h1>
        <p class="hero-subtitle">让每一份教学内容都拥有声音的温度</p>
        <div class="hero-actions">
          <!-- 未登录：单一引导 CTA -->
          <a-button
            v-if="!auth.isAuthenticated"
            size="large"
            class="hero-btn"
            @click="router.push('/login')"
          >
            登录 / 注册
          </a-button>
          <!-- 已登录：双 CTA —— 开始创作 + 浏览课件库 -->
          <template v-else>
            <a-button
              size="large"
              class="hero-btn"
              @click="router.push('/tts')"
            >
              开始创作
            </a-button>
            <a-button
              size="large"
              class="hero-btn hero-btn-ghost"
              @click="router.push('/courseware')"
            >
              浏览课件库
            </a-button>
          </template>
        </div>
      </div>
    </div>

    <!-- 功能卡片：图标改渐变芯片式（56px 圆角方块） -->
    <div class="feature-grid">
      <a-card
        v-for="f in features"
        :key="f.path"
        class="feature-card hover-card"
        hoverable
        role="link"
        tabindex="0"
        @click="router.push(f.path)"
        @keydown.enter.prevent="router.push(f.path)"
        @keydown.space.prevent="router.push(f.path)"
      >
        <div class="feature-chip">
          <component :is="f.icon" />
        </div>
        <h3 class="feature-title">{{ f.title }}</h3>
        <p class="feature-desc">{{ f.desc }}</p>
      </a-card>
    </div>
  </div>
</template>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #ff9a5a 0%, #ff6b35 45%, #e85d2a 100%);
  border-radius: 16px;
  padding: 48px 40px;
  color: #fff;
  margin-bottom: 24px;
}
.hero-content {
  position: relative;
  z-index: 1;
}
.hero-deco {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
}
.hero-deco-1 {
  width: 180px;
  height: 180px;
  top: -60px;
  right: -40px;
}
.hero-deco-2 {
  width: 120px;
  height: 120px;
  bottom: -50px;
  right: 160px;
  background: rgba(255, 255, 255, 0.08);
}
.hero-title {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 8px;
}
.hero-subtitle {
  font-size: 16px;
  margin: 0 0 20px;
  opacity: 0.95;
}
.hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.hero-btn {
  background: #fff;
  color: #c94f1f;
  border: none;
  font-weight: 500;
}
.hero-btn:hover {
  color: #e85d2a;
  border: none;
}
/* 幽灵按钮：半透明玻璃质感，用于次要 CTA */
.hero-btn-ghost {
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.4);
}
.hero-btn-ghost:hover {
  background: rgba(255, 255, 255, 0.28);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.6);
}
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}
.feature-card {
  cursor: pointer;
  text-align: center;
  border-radius: 12px;
}
/* 渐变芯片式图标容器：56px 圆角方块 */
.feature-chip {
  width: 56px;
  height: 56px;
  margin: 0 auto 12px;
  border-radius: 14px;
  background: linear-gradient(135deg, #ffe8d9 0%, #ffd6bc 100%);
  color: #e85d2a;
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.feature-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px;
  color: #2b2724;
}
.feature-desc {
  color: #6b6460;
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}
.feature-card:focus-visible {
  outline: 2px solid #ff6b35;
  outline-offset: 2px;
}
</style>
