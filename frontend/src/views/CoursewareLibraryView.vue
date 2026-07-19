<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { listCourseware, type CoursewareProject } from "../api/courseware";

const router = useRouter();
const presets = ref<CoursewareProject[]>([]);
const myProjects = ref<CoursewareProject[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    const [p, m] = await Promise.all([
      listCourseware("preset"),
      listCourseware("my"),
    ]);
    presets.value = p.projects;
    myProjects.value = m.projects;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <a-spin :spinning="loading">
    <a-typography-title :level="3">课件库</a-typography-title>
    <a-button type="primary" @click="router.push('/courseware/new')" style="margin-bottom: 16px">
      创建新课件
    </a-button>

    <a-typography-title :level="4">官方示例</a-typography-title>
    <a-row :gutter="16">
      <a-col v-for="p in presets" :key="p.id" :span="6">
        <a-card :title="p.title" hoverable @click="router.push(`/courseware/${p.id}`)">
          <p>{{ p.description }}</p>
          <a-tag color="blue">官方示例</a-tag>
        </a-card>
      </a-col>
    </a-row>

    <a-typography-title :level="4" style="margin-top: 24px">我的课件</a-typography-title>
    <a-row :gutter="16">
      <a-col v-for="p in myProjects" :key="p.id" :span="6">
        <a-card :title="p.title" hoverable @click="router.push(`/courseware/${p.id}`)">
          <a-tag :color="p.status === 'completed' ? 'green' : 'orange'">{{ p.status }}</a-tag>
          <p>{{ p.slides_count }} 页</p>
        </a-card>
      </a-col>
    </a-row>
    <a-empty v-if="myProjects.length === 0" description="还没有创建课件" />
  </a-spin>
</template>
