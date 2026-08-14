<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { listCourseware, type CoursewareProject } from "../api/courseware";
import apiClient from "../api/client";
import {
  BookOutlined,
  FileTextOutlined,
  PlusOutlined,
} from "@ant-design/icons-vue";

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

    <!-- 官方示例：橙色计数徽章 + 卡片渐变封面条 -->
    <div class="section-head">
      <h2 class="section-title">官方示例</h2>
      <span class="count-badge">{{ presets.length }}</span>
    </div>
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
        <div class="card-cover cover-preset" aria-hidden="true"></div>
        <div class="card-body">
          <h3 class="card-title">{{ p.title }}</h3>
          <p class="card-desc">{{ p.description || "暂无描述" }}</p>
          <a-tag color="orange">官方示例</a-tag>
        </div>
      </a-card>
      <!-- 空状态：米色虚线引导区 -->
      <div v-if="!presets.length" class="empty-guide">
        <BookOutlined class="empty-icon" />
        <p class="empty-text">暂无官方示例</p>
      </div>
    </div>

    <!-- 我的课件 -->
    <div class="section-head" style="margin-top: 32px">
      <h2 class="section-title">我的课件</h2>
      <span class="count-badge">{{ myProjects.length }}</span>
    </div>
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
        <div class="card-cover cover-my" aria-hidden="true"></div>
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
      <!-- 空状态：米色虚线引导区 + 行动按钮 -->
      <div v-if="myProjects.length === 0" class="empty-guide">
        <FileTextOutlined class="empty-icon" />
        <p class="empty-text">还没有创建课件</p>
        <a-button type="primary" @click="router.push('/courseware/new')">
          <template #icon><PlusOutlined /></template>
          上传第一个课件
        </a-button>
      </div>
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
  color: #2b2724;
}
.section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px;
}
.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: #2b2724;
}
/* 橙色计数徽章 */
.count-badge {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: linear-gradient(135deg, #ff8a4c 0%, #ff6b35 100%);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  line-height: 20px;
  text-align: center;
  display: inline-block;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
.preset-card:focus-visible,
.my-card:focus-visible {
  outline: 2px solid #ff6b35;
  outline-offset: 2px;
}
/* 卡片顶部品牌渐变封面条：官方浅 / 我的深 */
.card-cover {
  height: 56px;
  border-radius: 12px 12px 0 0;
  margin: -1px -1px 0;
}
.cover-preset {
  background: linear-gradient(135deg, #ffe8d9 0%, #ffd6bc 100%);
}
.cover-my {
  background: linear-gradient(135deg, #ff8a4c 0%, #ff6b35 50%, #e85d2a 100%);
}
.card-grid > :deep(.ant-empty) {
  grid-column: 1 / -1;
}
.card-body {
  min-height: 120px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 8px;
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
  color: #2b2724;
}
.card-desc {
  color: #6b6460;
  font-size: 13px;
  margin: 0;
  flex: 1;
}
/* 空状态：米色虚线引导区 */
.empty-guide {
  grid-column: 1 / -1;
  min-height: 160px;
  border: 1.5px dashed #e3d8cf;
  border-radius: 12px;
  background: #fff7f2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px;
  text-align: center;
}
.empty-icon {
  font-size: 36px;
  color: #ffb26b;
}
.empty-text {
  color: #6b6460;
  font-size: 14px;
  margin: 0;
}
</style>
