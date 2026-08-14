import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("../views/HomeView.vue"),
      meta: { title: "灵犀语伴 — AI 语音合成教学平台" },
    },
    {
      path: "/tts",
      name: "tts",
      component: () => import("../views/TtsView.vue"),
      meta: { title: "文本转语音 — 灵犀语伴" },
    },
    {
      path: "/login",
      name: "login",
      component: () => import("../views/LoginView.vue"),
      meta: { title: "登录 / 注册 — 灵犀语伴" },
    },
    {
      path: "/courseware",
      name: "courseware-library",
      component: () => import("../views/CoursewareLibraryView.vue"),
      meta: { title: "课件库 — 灵犀语伴", requiresAuth: true },
    },
    {
      path: "/courseware/new",
      name: "courseware-new",
      component: () => import("../views/CoursewareView.vue"),
      meta: { title: "创建新课件 — 灵犀语伴", requiresAuth: true },
    },
    {
      path: "/courseware/:id",
      name: "courseware-edit",
      component: () => import("../views/CoursewareView.vue"),
      meta: { title: "课件详情 — 灵犀语伴", requiresAuth: true },
    },
    // 404 兜底：未匹配的路由都走这里，避免白屏
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("../views/NotFoundView.vue"),
      meta: { title: "页面不存在 — 灵犀语伴" },
    },
  ],
});

// 路由守卫：未登录访问受保护路由时重定向到登录页
router.beforeEach((to) => {
  const hasToken = !!localStorage.getItem("access_token");
  if (to.meta.requiresAuth && !hasToken) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  // 已登录访问登录页时直接进首页
  if (to.name === "login" && hasToken) {
    return { name: "home" };
  }
  return true;
});

// 页面标题随路由变化
router.afterEach((to) => {
  document.title = (to.meta.title as string) || "灵犀语伴";
});

export default router;
