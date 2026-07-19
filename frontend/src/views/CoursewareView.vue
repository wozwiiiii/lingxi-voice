<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  uploadPPTX,
  listCourseware,
  getSlides,
  patchSlide,
  startSynthesis,
  downloadCourseware,
  type CoursewareProject,
  type CoursewareSlide,
} from "../api/courseware";

const route = useRoute();
const router = useRouter();

const projectId = route.params.id as string | undefined;
const isNew = route.name === "courseware-new";

const project = ref<CoursewareProject | null>(null);
const slides = ref<CoursewareSlide[]>([]);
const loading = ref(false);

async function loadProject() {
  if (!projectId) return;
  loading.value = true;
  try {
    slides.value = await getSlides(projectId);
  } finally {
    loading.value = false;
  }
}

async function handleFileUpload(file: File) {
  const proj = await uploadPPTX(file);
  router.push(`/courseware/${proj.id}`);
}

async function handleSynthesize() {
  if (!projectId) return;
  await startSynthesis(projectId);
}

async function handleDownload() {
  if (!projectId) return;
  const blob = await downloadCourseware(projectId);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${projectId}.zip`;
  a.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <a-spin :spinning="loading">
    <a-typography-title :level="3">
      {{ isNew ? "创建新课件" : "编辑课件" }}
    </a-typography-title>

    <template v-if="isNew">
      <a-upload
        accept=".pptx"
        :before-upload="(file: File) => { handleFileUpload(file); return false; }"
      >
        <a-button type="primary">上传 PPTX 文件</a-button>
      </a-upload>
    </template>

    <template v-else-if="slides.length > 0">
      <a-space style="margin-bottom: 16px">
        <a-button type="primary" @click="handleSynthesize">一键合成</a-button>
        <a-button @click="handleDownload">下载课件</a-button>
      </a-space>

      <a-table :data-source="slides" :columns="[
        { title: '页码', dataIndex: 'slide_index', key: 'slide_index' },
        { title: '原文', dataIndex: 'original_text', key: 'original_text' },
        { title: '状态', dataIndex: 'status', key: 'status' },
      ]" row-key="id" />
    </template>
  </a-spin>
</template>
