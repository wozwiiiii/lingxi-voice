<script setup lang="ts">
import { ref, onMounted } from "vue";
import { message } from "ant-design-vue";
import { synthesizeTTS, getVoices } from "../api/tts";
import type { VoiceResponse } from "../types";

const text = ref("");
const selectedVoice = ref<string>("");
const voices = ref<VoiceResponse[]>([]);
const audioUrl = ref<string | null>(null);
const audioFileName = ref("");
const loading = ref(false);

// Synthesis history — persists in localStorage
interface HistoryItem { text: string; voiceName: string; url: string; fileName: string; time: string }
const STORAGE_KEY = "lingxi_tts_history";

// 安全读取历史：localStorage 数据损坏时兜底为空数组，避免整页白屏
function loadHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
const history = ref<HistoryItem[]>(loadHistory());

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
  try { voices.value = await getVoices(); }
  catch { message.error("无法加载声音列表"); }
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
  try {
    const res = await synthesizeTTS({ text: text.value, voice_id: selectedVoice.value });
    // 后端返回相对路径 /media/...，直接使用以适配部署地址（dev 走 vite 代理，生产走 nginx）
    audioUrl.value = res.audio_url;
    audioFileName.value = `tts_${Date.now()}.mp3`;
    history.value.unshift({
      text: text.value.substring(0, 50),
      voiceName: voiceName(selectedVoice.value),
      url: audioUrl.value!,
      fileName: audioFileName.value,
      time: new Date().toLocaleString("zh-CN"),
    });
    saveHistory();
    message.success("合成完成");
  } catch (e: any) {
    message.error(e.response?.data?.detail || "合成失败");
  } finally {
    loading.value = false;
  }
}

onMounted(loadVoices);
</script>

<template>
  <h1 class="page-title">文本转语音</h1>
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
                <a-button type="link" size="small" @click="replayAudio(item)">播放</a-button>
              </template>
            </a-list-item>
          </template>
        </a-list>
      </a-card>
    </a-col>

    <!-- 右侧：预览 -->
    <a-col :xs="24" :lg="12" class="preview-col">
      <a-card class="panel preview-panel" :bordered="false">
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
        <a-empty v-else class="lx-empty" description="合成语音后将在此播放" />
      </a-card>
    </a-col>
  </a-row>
</template>

<style scoped>
.page-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 16px;
  color: var(--lx-text);
}
.panel {
  background: var(--lx-surface);
  border-radius: 12px;
  margin-bottom: 16px;
}
.panel-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--lx-text);
}
/* 预览面板与左侧等高，消除大片留白 */
.preview-panel {
  height: 100%;
  margin-bottom: 0;
}
@media (max-width: 991px) {
  .preview-col {
    order: -1;
  }
}
</style>
