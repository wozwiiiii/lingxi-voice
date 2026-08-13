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
  <div>
    <!-- 欢迎区域 -->
    <div class="hero">
      <h1 class="hero-title">
        {{ auth.isAuthenticated ? `您好，${auth.user?.username}！` : "欢迎来到灵犀语伴" }}
      </h1>
      <p class="hero-subtitle">让每一份教学内容都拥有声音的温度</p>
      <a-button
        v-if="!auth.isAuthenticated"
        size="large"
        class="hero-btn"
        @click="router.push('/login')"
      >
        登录 / 注册
      </a-button>
      <a-button
        v-else
        size="large"
        class="hero-btn"
        @click="router.push('/tts')"
      >
        开始使用
      </a-button>
    </div>

    <!-- 功能卡片 -->
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
        <div class="feature-icon">
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
  background: linear-gradient(135deg, #e64a19 0%, #d84315 100%);
  border-radius: 16px;
  padding: 48px 32px;
  color: #fff;
  margin-bottom: 24px;
}
.hero-title {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 8px;
}
.hero-subtitle {
  font-size: 16px;
  margin: 0 0 20px;
}
.hero-btn {
  background: #fff;
  color: #bf360c;
  border: none;
  font-weight: 500;
}
.hero-btn:hover {
  color: #8a2b0b;
  border: none;
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
.feature-icon {
  font-size: 36px;
  color: #ff7043;
  margin-bottom: 12px;
}
.feature-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px;
  color: #424242;
}
.feature-desc {
  color: #757575;
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}
.feature-card:focus-visible {
  outline: 2px solid #ff7043;
  outline-offset: 2px;
}
</style>
