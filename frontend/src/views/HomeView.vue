<template>
  <a-typography>
    <a-typography-title>灵犀语伴 — AI 语音合成教学平台</a-typography-title>
    <a-typography-paragraph>
      基于 CosyVoice2 深度学习模型，提供文本转语音、声音克隆、有声课件制作等功能。
      支持 16 种情感风格、中英日韩粤多语言、零样本声音克隆。
    </a-typography-paragraph>
    <a-space>
      <a-button type="primary" size="large" @click="$router.push('/tts')">开始使用</a-button>
      <a-button size="large" @click="$router.push('/login')">登录 / 注册</a-button>
    </a-space>
  </a-typography>
</template>
