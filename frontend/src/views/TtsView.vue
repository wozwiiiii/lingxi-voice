<script setup lang="ts">
import { ref, onMounted } from "vue";
import { synthesizeTTS, getVoices } from "../api/tts";
import type { VoiceResponse } from "../types";

const text = ref("");
const selectedVoice = ref<string>("");
const voices = ref<VoiceResponse[]>([]);
const audioUrl = ref<string | null>(null);
const loading = ref(false);
const error = ref("");

async function loadVoices() {
  try {
    voices.value = await getVoices();
  } catch {
    error.value = "无法加载声音列表";
  }
}

async function handleSynthesize() {
  if (!text.value || !selectedVoice.value) return;
  loading.value = true;
  error.value = "";
  try {
    const res = await synthesizeTTS({ text: text.value, voice_id: selectedVoice.value });
    audioUrl.value = res.audio_url;
  } catch (e: any) {
    error.value = e.response?.data?.detail || "合成失败";
  } finally {
    loading.value = false;
  }
}

onMounted(loadVoices);
</script>

<template>
  <a-row :gutter="24">
    <a-col :span="12">
      <a-card title="文本转语音">
        <a-textarea
          v-model:value="text"
          :rows="6"
          placeholder="请输入要合成的文本..."
          :maxlength="1000"
        />
        <a-space style="margin-top: 12px" direction="vertical">
          <a-select
            v-model:value="selectedVoice"
            placeholder="选择声音"
            style="width: 260px"
          >
            <a-select-option v-for="v in voices" :key="v.id" :value="v.id">
              {{ v.name }} ({{ v.type === "preset" ? "预设" : "克隆" }})
            </a-select-option>
          </a-select>
          <a-button type="primary" :loading="loading" @click="handleSynthesize">合成</a-button>
        </a-space>
        <a-alert
          v-if="error"
          type="error"
          :message="error"
          style="margin-top: 12px"
          closable
          @close="error = ''"
        />
      </a-card>
    </a-col>
    <a-col :span="12">
      <a-card title="音频播放">
        <audio v-if="audioUrl" controls :src="audioUrl" style="width: 100%">
          您的浏览器不支持音频播放
        </audio>
        <a-empty v-else description="合成语音后将在此播放" />
      </a-card>
    </a-col>
  </a-row>
</template>
