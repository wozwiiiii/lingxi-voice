<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getVoices, type VoiceResponse } from "../api/tts";
import {
  uploadPPTX, getSlides, patchSlide, startSynthesis, downloadCourseware,
  type CoursewareSlide,
} from "../api/courseware";
import apiClient from "../api/client";

const route = useRoute();
const router = useRouter();
const projectId = route.params.id as string | undefined;
const isNew = route.name === "courseware-new";

const title = ref("");
const slides = ref<CoursewareSlide[]>([]);
const voices = ref<VoiceResponse[]>([]);
const loading = ref(false);
const error = ref("");
const synthesizing = ref(false);

onMounted(async () => {
  if (!isNew && projectId) await loadProject();
  try { voices.value = await getVoices(); } catch { /* ignore */ }
});

async function loadProject() {
  loading.value = true;
  try {
    slides.value = await getSlides(projectId!);
    try {
      const r = await apiClient.get(`/courseware/${projectId}`);
      title.value = r.data.title;
    } catch { /* preset may not have slides */ }
  } catch (e: any) {
    error.value = e.response?.status === 404 ? "课件不存在或无权访问" : "加载失败";
  } finally { loading.value = false; }
}

async function handleFileUpload(file: File) {
  loading.value = true;
  try {
    const proj = await uploadPPTX(file);
    router.push(`/courseware/${proj.id}`);
  } catch (e: any) {
    error.value = e.response?.data?.detail || "上传失败";
  } finally { loading.value = false; }
}

async function saveSlide(slide: CoursewareSlide) {
  if (!projectId) return;
  try {
    await patchSlide(projectId, slide.slide_index, {
      edited_text: slide.edited_text,
      voice_id: slide.voice_id,
    });
  } catch { /* ignore */ }
}

async function handleSynthesize() {
  if (!projectId) return;
  synthesizing.value = true;
  error.value = "";
  try {
    const result = await startSynthesis(projectId);
    if (result.status === "completed") {
      error.value = `合成完成！共 ${slides.value.length} 页`;
      await loadProject(); // Reload slide statuses
    } else {
      error.value = result.message || "合成结束，部分页面可能失败";
      await loadProject();
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || "合成失败，请重试";
    await loadProject(); // Reload anyway to show failed slides
  } finally { synthesizing.value = false; }
}

async function handleDownload() {
  if (!projectId) return;
  try {
    const blob = await downloadCourseware(projectId);
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
    error.value = e.response?.data?.detail || e.message || "下载失败";
  }
}

async function handleDelete() {
  if (!projectId || !confirm("确定删除此课件？")) return;
  try {
    await apiClient.delete(`/courseware/${projectId}`);
    router.push("/courseware");
  } catch (e: any) {
    error.value = e.response?.data?.detail || "删除失败";
  }
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
          <div class="upload-icon" aria-hidden="true">📄</div>
          <h3 class="upload-title">上传 PPTX 课件</h3>
          <p class="upload-hint">仅支持 .pptx 格式，大小不超过 20MB</p>
          <a-upload
            accept=".pptx"
            :before-upload="(file: any) => { handleFileUpload(file); return false }"
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
    <a-empty v-else description="此课件暂无内容" />
  </a-spin>
</template>

<style scoped>
.page-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 16px;
  color: #2b2724;
}
.upload-card {
  max-width: 560px;
  border-radius: 16px;
  background: #fff7f2;
}
.upload-body {
  text-align: center;
  padding: 32px 16px;
}
.upload-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.upload-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px;
  color: #2b2724;
}
.upload-hint {
  color: #6b6460;
  font-size: 13px;
  margin: 0 0 20px;
}
</style>
