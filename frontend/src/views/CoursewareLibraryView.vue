<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { listCourseware, type CoursewareProject } from "../api/courseware";
import apiClient from "../api/client";

const router = useRouter();
const presets = ref<CoursewareProject[]>([]);
const myProjects = ref<CoursewareProject[]>([]);
const loading = ref(false);

// 状态码 → 中文标签 + 颜色
function statusLabel(status: string): string {
  const map: Record<string, string> = {
    completed: "已完成",
    synthesizing: "合成中",
    failed: "合成失败",
    pending: "待合成",
    ready: "待合成",
    parsing: "解析中",
  };
  return map[status] || status;
}

function statusColor(status: string): string {
  if (status === "completed") return "green";
  if (status === "failed") return "red";
  if (status === "synthesizing") return "orange";
  if (status === "parsing") return "blue";
  return "default";
}

async function load() {
  loading.value = true;
  try {
    const [p, m] = await Promise.all([listCourseware("preset"), listCourseware("my")]);
    presets.value = p.projects;
    myProjects.value = m.projects;
  } finally { loading.value = false; }
}

async function deleteMy(id: string, title: string) {
  if (!confirm(`确定删除"${title}"？此操作不可恢复。`)) return;
  try {
    await apiClient.delete(`/courseware/${id}`);
    myProjects.value = myProjects.value.filter(p => p.id !== id);
  } catch (e: any) { alert(e.response?.data?.detail || "删除失败"); }
}

onMounted(load);
</script>

<template>
  <a-spin :spinning="loading">
    <div class="page-head">
      <h1 class="page-title">课件库</h1>
      <a-button type="primary" size="large" @click="router.push('/courseware/new')">
        创建新课件
      </a-button>
    </div>

    <h2 class="section-title">官方示例</h2>
    <div class="card-grid">
      <a-card
        v-for="p in presets"
        :key="p.id"
        class="hover-card preset-card"
        hoverable
        role="link"
        tabindex="0"
        @click="router.push(`/courseware/${p.id}`)"
        @keydown.enter.prevent="router.push(`/courseware/${p.id}`)"
        @keydown.space.prevent="router.push(`/courseware/${p.id}`)"
      >
        <div class="card-body">
          <h3 class="card-title">{{ p.title }}</h3>
          <p class="card-desc">{{ p.description || "暂无描述" }}</p>
          <a-tag color="orange">官方示例</a-tag>
        </div>
      </a-card>
      <a-empty v-if="!presets.length" description="暂无官方示例" />
    </div>

    <h2 class="section-title" style="margin-top: 32px">我的课件</h2>
    <div class="card-grid">
      <a-card
        v-for="p in myProjects"
        :key="p.id"
        class="hover-card my-card"
        hoverable
        role="link"
        tabindex="0"
        @click="router.push(`/courseware/${p.id}`)"
        @keydown.enter.prevent="router.push(`/courseware/${p.id}`)"
        @keydown.space.prevent="router.push(`/courseware/${p.id}`)"
      >
        <div class="card-body">
          <div class="card-title-row">
            <h3 class="card-title">{{ p.title }}</h3>
            <a-tag :color="statusColor(p.status)">{{ statusLabel(p.status) }}</a-tag>
          </div>
          <p class="card-desc">{{ p.slides_count }} 页</p>
          <a-space>
            <a-button
              size="small"
              type="primary"
              @click.stop="router.push(`/courseware/${p.id}`)"
              @keydown.stop
            >
              编辑
            </a-button>
            <a-button
              size="small"
              danger
              @click.stop="deleteMy(p.id, p.title)"
              @keydown.stop
            >
              删除
            </a-button>
          </a-space>
        </div>
      </a-card>
      <a-empty v-if="myProjects.length === 0" description="还没有创建课件" />
    </div>
  </a-spin>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.page-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
  color: #424242;
}
.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px;
  color: #424242;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
.preset-card:focus-visible,
.my-card:focus-visible {
  outline: 2px solid #ff7043;
  outline-offset: 2px;
}
.card-grid > :deep(.ant-empty) {
  grid-column: 1 / -1;
}
.card-body {
  min-height: 120px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: #424242;
}
.card-desc {
  color: #757575;
  font-size: 13px;
  margin: 0;
  flex: 1;
}
</style>
