<script setup lang="ts">
import { ref, onMounted } from "vue";
import { message } from "ant-design-vue";
import { synthesizeTTS, getVoices, cloneVoice, getHistory } from "../api/tts";
import type { VoiceResponse } from "../types";

const text = ref("");
const selectedVoice = ref<string>("");
const voices = ref<VoiceResponse[]>([]);
const audioUrl = ref<string | null>(null);
const audioFileName = ref("");
const loading = ref(false);

// ---- 声音克隆 ----
const cloneModalVisible = ref(false);
const cloneName = ref("");
const clonePurpose = ref("");
const cloneDescription = ref("");
const cloneFile = ref<File | null>(null);
const cloneLoading = ref(false);

function resetCloneForm() {
  cloneName.value = "";
  clonePurpose.value = "";
  cloneDescription.value = "";
  cloneFile.value = null;
}

function beforeCloneUpload(file: File) {
  // 前端只做基础校验，真正的格式/时长/质量门在后端
  cloneFile.value = file;
  return false; // 阻止自动上传，交给 submit 手动发
}

async function handleClone() {
  if (!cloneFile.value || !cloneName.value.trim()) {
    message.warning("请填写声音名称并选择音频文件");
    return;
  }
  if (clonePurpose.value.trim().length < 5) {
    message.warning("请填写声音用途（至少 5 个字，作为授权声明）");
    return;
  }
  cloneLoading.value = true;
  try {
    const res = await cloneVoice({
      file: cloneFile.value,
      name: cloneName.value.trim(),
      purpose: clonePurpose.value.trim(),
      description: cloneDescription.value.trim() || undefined,
    });
    message.success("声音克隆成功，已加入列表");
    cloneModalVisible.value = false;
    resetCloneForm();
    await loadVoices(); // 刷新列表，新克隆的声音出现在下拉框
    if (res.voice_id) selectedVoice.value = res.voice_id;
  } catch (e: any) {
    message.error(e.response?.data?.detail || "克隆失败，请检查音频格式（支持 MP3/WAV/FLAC/OGG）");
  } finally {
    cloneLoading.value = false;
  }
}

// Synthesis history — 登录用户走云端（/api/tts/history），游客降级 localStorage
interface HistoryItem { text: string; voiceName: string; url: string; fileName: string; time: string }
const STORAGE_KEY = "lingxi_tts_history";

function isLoggedIn(): boolean {
  return !!localStorage.getItem("access_token");
}

// 安全读取本地历史：localStorage 数据损坏时兜底为空数组，避免整页白屏
function loadLocalHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
const history = ref<HistoryItem[]>([]);

function saveLocalHistory() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history.value.slice(0, 20)));
}

// 加载历史：登录用户从云端拉取（换设备不丢），游客读本地缓存
async function loadHistory() {
  if (!isLoggedIn()) {
    history.value = loadLocalHistory();
    return;
  }
  try {
    const items = await getHistory();
    history.value = items
      .filter((h) => h.audio_url)
      .map((h) => ({
        text: h.text.substring(0, 50),
        voiceName: "", // 云端历史不含 voiceName，展示时用 text + time
        url: h.audio_url!,
        fileName: `tts_${h.id}.mp3`,
        time: h.created_at ? new Date(h.created_at).toLocaleString("zh-CN") : "",
      }));
  } catch {
    // 云端拉取失败（如网络抖动）时降级本地缓存，避免历史区域空白
    history.value = loadLocalHistory();
  }
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
    if (isLoggedIn()) {
      // 登录用户：云端已落库，直接重拉历史（含刚合成的一条）
      await loadHistory();
    } else {
      // 游客：本地追加
      history.value.unshift({
        text: text.value.substring(0, 50),
        voiceName: voiceName(selectedVoice.value),
        url: audioUrl.value!,
        fileName: audioFileName.value,
        time: new Date().toLocaleString("zh-CN"),
      });
      saveLocalHistory();
    }
    message.success("合成完成");
  } catch (e: any) {
    message.error(e.response?.data?.detail || "合成失败");
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadVoices();
  loadHistory();
});
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
        <a-button
          type="link"
          size="small"
          style="padding-left: 0"
          @click="cloneModalVisible = true"
        >
          + 克隆我的声音
        </a-button>

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

  <!-- 声音克隆弹窗 -->
  <a-modal
    v-model:open="cloneModalVisible"
    title="克隆我的声音"
    :confirm-loading="cloneLoading"
    ok-text="开始克隆"
    cancel-text="取消"
    @ok="handleClone"
  >
    <a-form layout="vertical">
      <a-form-item label="声音名称" required>
        <a-input v-model:value="cloneName" placeholder="例如：我的课堂声音" :maxlength="200" />
      </a-form-item>
      <a-form-item label="参考音频" required>
        <a-upload
          :before-upload="beforeCloneUpload"
          :show-upload-list="false"
          accept="audio/*,.mp3,.wav,.flac,.ogg"
        >
          <a-button>{{ cloneFile ? cloneFile.name : "选择音频文件" }}</a-button>
        </a-upload>
        <div class="clone-hint">支持 MP3 / WAV / FLAC / OGG，时长 3-30 秒（清晰、无噪音的干声最佳）</div>
      </a-form-item>
      <a-form-item label="声音用途（授权声明）" required>
        <a-textarea
          v-model:value="clonePurpose"
          :rows="3"
          :maxlength="500"
          placeholder="请说明该克隆声音将用于什么用途（例如：仅用于我的教学课件制作）"
        />
      </a-form-item>
      <a-form-item label="描述（可选）">
        <a-input v-model:value="cloneDescription" placeholder="补充说明" :maxlength="500" />
      </a-form-item>
    </a-form>
  </a-modal>
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
.clone-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--lx-text-muted, #888);
}
</style>
