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

// Synthesis history — persists in localStorage
interface HistoryItem { text: string; voiceName: string; url: string; fileName: string; time: string }
const STORAGE_KEY = "lingxi_tts_history";
const history = ref<HistoryItem[]>(
  JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]")
);

function saveHistory() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history.value.slice(0, 20)));
}

const audioKey = ref(0); // forces <audio> to reload on change

function voiceName(id: string) {
  return voices.value.find(v => v.id === id)?.name || id;
}

function replayAudio(item: HistoryItem) {
  audioUrl.value = item.url;
  audioFileName.value = item.fileName;
  audioKey.value++;
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
    saveHistory();
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
    <!-- 左侧：输入面板 -->
    <a-col :xs="24" :lg="12">
      <a-card class="panel" :bordered="false">
        <h3 class="panel-title">文本内容</h3>
        <a-textarea
          v-model:value="text"
          :rows="8"
          :maxlength="1000"
          show-count
          placeholder="请输入要合成的文本..."
        />

        <h3 class="panel-title" style="margin-top: 16px">选择声音</h3>
        <a-select v-model:value="selectedVoice" placeholder="选择声音" style="width: 100%">
          <a-select-option v-for="v in voices" :key="v.id" :value="v.id">
            {{ v.name }}（{{ v.type === "preset" ? "预设" : "克隆" }}）
          </a-select-option>
        </a-select>

        <a-space style="margin-top: 16px">
          <a-button
            type="primary"
            size="large"
            :loading="loading"
            :disabled="!text || !selectedVoice"
            @click="handleSynthesize"
          >
            开始合成
          </a-button>
          <a-button v-if="audioUrl" size="large" @click="downloadAudio">下载音频</a-button>
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

      <!-- 历史记录 -->
      <a-card class="panel" :bordered="false" v-if="history.length">
        <h3 class="panel-title">历史记录</h3>
        <a-list :data-source="history" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta
                :title="item.text"
                :description="`${item.voiceName} · ${item.time}`"
              />
              <template #actions>
                <a @click="replayAudio(item)">播放</a>
              </template>
            </a-list-item>
          </template>
        </a-list>
      </a-card>
    </a-col>

    <!-- 右侧：预览 -->
    <a-col :xs="24" :lg="12">
      <a-card class="panel" :bordered="false">
        <h3 class="panel-title">音频预览</h3>
        <audio
          v-if="audioUrl"
          :key="audioKey"
          controls
          :src="audioUrl"
          style="width: 100%"
        >
          不支持音频播放
        </audio>
        <a-empty v-else description="合成语音后将在此播放" />
      </a-card>
    </a-col>
  </a-row>
</template>

<style scoped>
.panel {
  background: #fff;
  border-radius: 12px;
  margin-bottom: 16px;
}
.panel-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
  color: #424242;
}
</style>
