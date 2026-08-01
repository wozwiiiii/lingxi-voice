<script setup lang="ts">
import { ref, onMounted } from "vue";
import { synthesizeTTS, getVoices } from "../api/tts";
import type { VoiceResponse } from "../types";

const text = ref("");
const selectedVoice = ref<string>("");
const voices = ref<VoiceResponse[]>([]);
const audioUrl = ref<string | null>(null);
const audioFileName = ref("");
const loading = ref(false);
const error = ref("");

// Synthesis history
interface HistoryItem { text: string; voiceName: string; url: string; fileName: string; time: string }
const history = ref<HistoryItem[]>([]);

function voiceName(id: string) {
  return voices.value.find(v => v.id === id)?.name || id;
}

async function loadVoices() {
  try { voices.value = await getVoices(); } catch { error.value = "无法加载声音列表"; }
}

function downloadAudio() {
  if (!audioUrl.value) return;
  const a = document.createElement("a");
  a.href = audioUrl.value;
  a.download = audioFileName.value || "audio.mp3";
  a.click();
}

async function handleSynthesize() {
  if (!text.value || !selectedVoice.value) return;
  loading.value = true;
  error.value = "";
  try {
    const res = await synthesizeTTS({ text: text.value, voice_id: selectedVoice.value });
    audioUrl.value = 'http://localhost' + res.audio_url;
    audioFileName.value = `tts_${Date.now()}.mp3`;
    history.value.unshift({
      text: text.value.substring(0, 50),
      voiceName: voiceName(selectedVoice.value),
      url: audioUrl.value!,
      fileName: audioFileName.value,
      time: new Date().toLocaleString("zh-CN"),
    });
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
        <a-textarea v-model:value="text" :rows="6" placeholder="请输入要合成的文本..." :maxlength="1000" />
        <a-space style="margin-top: 12px" direction="vertical">
          <a-select v-model:value="selectedVoice" placeholder="选择声音" style="width: 260px">
            <a-select-option v-for="v in voices" :key="v.id" :value="v.id">
              {{ v.name }} ({{ v.type === "preset" ? "预设" : "克隆" }})
            </a-select-option>
          </a-select>
          <a-space>
            <a-button type="primary" :loading="loading" @click="handleSynthesize">合成</a-button>
            <a-button v-if="audioUrl" @click="downloadAudio">下载音频</a-button>
          </a-space>
        </a-space>
        <a-alert v-if="error" type="error" :message="error" style="margin-top:12px" closable @close="error=''" />
      </a-card>

      <a-card title="历史记录" style="margin-top:16px" v-if="history.length">
        <a-list :data-source="history" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta :title="item.text" :description="`${item.voiceName} · ${item.time}`" />
            </a-list-item>
          </template>
        </a-list>
      </a-card>
    </a-col>
    <a-col :span="12">
      <a-card title="音频播放">
        <audio v-if="audioUrl" controls :src="audioUrl" style="width:100%">不支持音频播放</audio>
        <a-empty v-else description="合成语音后将在此播放" />
      </a-card>
    </a-col>
  </a-row>
</template>
