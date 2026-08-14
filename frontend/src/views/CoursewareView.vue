<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { message, Modal } from "ant-design-vue";
import { FileTextOutlined } from "@ant-design/icons-vue";
import { getVoices, type VoiceResponse } from "../api/tts";
import {
  uploadPPTX, getSlides, patchSlide, startSynthesis, getSynthesisProgress, downloadCourseware,
  type CoursewareSlide,
} from "../api/courseware";
import apiClient from "../api/client";

const route = useRoute();
const router = useRouter();
// 响应式：/courseware/a → /courseware/b 切换（组件复用）时也能拿到新 id
const projectId = computed(() => route.params.id as string | undefined);
const isNew = computed(() => route.name === "courseware-new");

const title = ref("");
const slides = ref<CoursewareSlide[]>([]);
const voices = ref<VoiceResponse[]>([]);
const loading = ref(false);
const error = ref("");
const synthesizing = ref(false);
const progressCurrent = ref(0);
const progressTotal = ref(0);

// 与后端 MAX_UPLOAD_SIZE_MB 保持一致
const MAX_UPLOAD_MB = 20;

function beforeUpload(file: File): boolean {
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    message.error(`文件超过 ${MAX_UPLOAD_MB}MB，请压缩后重试`);
    return false;
  }
  handleFileUpload(file);
  return false; // 阻止自动上传，由 handleFileUpload 手动处理
}

async function loadProject() {
  if (!projectId.value) return;
  loading.value = true;
  error.value = "";
  try {
    slides.value = await getSlides(projectId.value);
    try {
      const r = await apiClient.get(`/courseware/${projectId.value}`);
      title.value = r.data.title;
    } catch { /* preset may not have slides */ }
  } catch (e: any) {
    error.value = e.response?.status === 404 ? "课件不存在或无权访问" : "加载失败";
  } finally { loading.value = false; }
}

onMounted(async () => {
  try { voices.value = await getVoices(); } catch { /* ignore */ }
  if (!isNew.value && projectId.value) await loadProject();
});

// 课件详情间切换：同一路由记录复用组件，onMounted 不重跑，需监听 id 变化重新加载
watch(projectId, (newId, oldId) => {
  if (isNew.value || !newId) return;
  if (newId !== oldId) {
    closeSynthesisStream(); // 切换课件时中止旧项目的进度流，避免串台
    synthesizing.value = false;
    loadProject();
  }
});

async function handleFileUpload(file: File) {
  loading.value = true;
  try {
    const proj = await uploadPPTX(file);
    router.push(`/courseware/${proj.id}`);
  } catch (e: any) {
    message.error(e.response?.data?.detail || "上传失败");
  } finally { loading.value = false; }
}

async function saveSlide(slide: CoursewareSlide) {
  if (!projectId.value) return;
  try {
    await patchSlide(projectId.value, slide.slide_index, {
      edited_text: slide.edited_text,
      voice_id: slide.voice_id,
    });
  } catch {
    // 保存失败不能静默吞掉，给用户明确反馈
    message.error(`第 ${slide.slide_index} 页保存失败，请重试`);
  }
}

let synthEventSource: EventSource | null = null;
let synthStreamEnded = false;

async function handleSynthesize() {
  if (!projectId.value || synthesizing.value) return; // 防止重复提交
  synthesizing.value = true;
  error.value = "";
  progressCurrent.value = 0;
  progressTotal.value = 0;
  try {
    const result = await startSynthesis(projectId.value);
    message.info(result.message || "合成任务已提交，正在后台合成");
    listenSynthesisProgress(projectId.value);
  } catch (e: any) {
    message.error(e.response?.data?.detail || "合成失败，请重试");
    synthesizing.value = false;
  }
}

// 通过 SSE 实时跟踪后台合成进度
function listenSynthesisProgress(pid: string) {
  closeSynthesisStream();
  synthStreamEnded = false;
  const es = getSynthesisProgress(pid);
  synthEventSource = es;

  es.onmessage = async (ev) => {
    let data: { current?: number; total?: number; status?: string };
    try {
      data = JSON.parse(ev.data);
    } catch {
      return; // 非 JSON 数据直接忽略
    }
    if (typeof data.current === "number") progressCurrent.value = data.current;
    if (typeof data.total === "number") progressTotal.value = data.total;

    if (data.status === "completed") {
      synthStreamEnded = true;
      closeSynthesisStream();
      message.success(`合成完成！共 ${data.total ?? slides.value.length} 页`);
      await loadProject(); // Reload slide statuses
      synthesizing.value = false;
    } else if (data.status === "failed") {
      synthStreamEnded = true;
      closeSynthesisStream();
      message.error("合成失败");
      await loadProject();
      synthesizing.value = false;
    }
  };

  es.onerror = () => {
    if (synthStreamEnded) return; // 正常结束(completed/failed)导致的连接关闭，忽略
    closeSynthesisStream();
    message.error("进度连接中断，请刷新页面查看合成状态");
    synthesizing.value = false;
    loadProject();
  };
}

function closeSynthesisStream() {
  synthEventSource?.close();
  synthEventSource = null;
}

onUnmounted(closeSynthesisStream);

async function handleDownload() {
  if (!projectId.value) return;
  try {
    const blob = await downloadCourseware(projectId.value);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.style.display = "none";
    a.href = url;
    a.download = title.value ? `${title.value}.zip` : "courseware.zip";
    document.body.appendChild(a);
    a.click();
    // Delay revoke to ensure browser starts download
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 150);
  } catch (e: any) {
    // Try to read error from blob response
    message.error(e.response?.data?.detail || e.message || "下载失败");
  }
}

function handleDelete() {
  if (!projectId.value) return;
  Modal.confirm({
    title: "删除课件",
    content: "确定删除此课件？此操作不可恢复。",
    okText: "删除",
    okType: "danger",
    cancelText: "取消",
    onOk: async () => {
      try {
        await apiClient.delete(`/courseware/${projectId.value}`);
        message.success("已删除");
        router.push("/courseware");
      } catch (e: any) {
        message.error(e.response?.data?.detail || "删除失败");
      }
    },
  });
}
</script>

<template>
  <a-spin :spinning="loading">
    <h1 class="page-title">
      {{ isNew ? "创建新课件" : (title || "课件详情") }}
    </h1>
    <a-alert v-if="error" type="info" :message="error" style="margin-bottom:12px" closable @close="error=''" />

    <!-- Upload mode -->
    <template v-if="isNew">
      <a-card class="upload-card" :bordered="false">
        <div class="upload-body">
          <div class="upload-icon" aria-hidden="true">
            <FileTextOutlined />
          </div>
          <h3 class="upload-title">上传 PPTX 课件</h3>
          <p class="upload-hint">仅支持 .pptx 格式，大小不超过 20MB</p>
          <a-upload
            accept=".pptx"
            :before-upload="beforeUpload"
            :show-upload-list="false"
          >
            <a-button type="primary" size="large">选择 PPTX 文件上传</a-button>
          </a-upload>
        </div>
      </a-card>
    </template>

    <!-- Editor mode -->
    <template v-else-if="slides.length > 0">
      <a-space style="margin-bottom:16px">
        <a-button type="primary" @click="handleSynthesize" :loading="synthesizing" :disabled="synthesizing">
          {{ synthesizing ? '正在合成中，请稍候...' : '一键合成' }}
        </a-button>
        <a-button @click="handleDownload" :disabled="synthesizing">下载课件</a-button>
        <a-button danger @click="handleDelete">删除课件</a-button>
      </a-space>

      <div v-if="synthesizing" class="synth-progress">
        合成中 {{ progressCurrent }}/{{ progressTotal }}
      </div>

      <div v-for="s in slides" :key="s.id" style="margin-bottom:12px">
        <a-card size="small" :title="`第 ${s.slide_index} 页`">
          <a-textarea v-model:value="s.edited_text"
            :placeholder="s.original_text || '(无文本内容，可手动输入)'" :rows="3"
            @blur="saveSlide(s)" />
          <a-select v-model:value="s.voice_id" placeholder="选择声音" style="width:200px;margin-top:4px"
            @change="saveSlide(s)" allow-clear>
            <a-select-option v-for="v in voices" :key="v.id" :value="v.id">{{ v.name }}</a-select-option>
          </a-select>
          <a-tag v-if="s.status==='completed'" color="green" style="margin-left:8px">已合成</a-tag>
          <a-tag v-else-if="s.status==='failed'" color="red" style="margin-left:8px">合成失败</a-tag>
          <a-tag v-else color="default" style="margin-left:8px">待合成</a-tag>
        </a-card>
      </div>
    </template>

    <!-- No slides (preset with 0 slides) -->
    <a-empty v-else class="lx-empty" description="此课件暂无内容" />
  </a-spin>
</template>

<style scoped>
.page-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 16px;
  color: var(--lx-text);
}
.upload-card {
  max-width: 560px;
  border-radius: 16px;
  background: var(--lx-surface);
}
.upload-body {
  text-align: center;
  padding: 32px 16px;
}
.upload-icon {
  font-size: 48px;
  color: var(--lx-primary);
  margin-bottom: 12px;
}
.upload-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--lx-text);
}
.upload-hint {
  color: var(--lx-text-secondary);
  font-size: 13px;
  margin: 0 0 20px;
}
.synth-progress {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--lx-text-secondary);
}
</style>
