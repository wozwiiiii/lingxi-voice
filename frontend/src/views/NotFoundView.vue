<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<template>
  <div class="not-found fade-up">
    <div class="not-found-code" aria-hidden="true">404</div>
    <h1 class="not-found-title">页面走丢了</h1>
    <p class="not-found-desc">您访问的页面不存在，可能已被移除或链接有误。</p>
    <a-space>
      <a-button type="primary" size="large" @click="router.push('/')">返回首页</a-button>
      <a-button size="large" @click="router.back()">返回上一页</a-button>
    </a-space>
  </div>
</template>

<style scoped>
.not-found {
  max-width: 560px;
  margin: 80px auto;
  text-align: center;
  padding: 48px 32px;
  background: var(--lx-surface);
  border-radius: 16px;
  border: 1px dashed var(--lx-border-strong);
}
.not-found-code {
  font-size: 72px;
  font-weight: 800;
  line-height: 1;
  background: var(--lx-gradient-brand);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  margin-bottom: 8px;
}
.not-found-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--lx-text);
  margin: 0 0 8px;
}
.not-found-desc {
  color: var(--lx-text-secondary);
  font-size: 15px;
  margin: 0 0 24px;
}
</style>
