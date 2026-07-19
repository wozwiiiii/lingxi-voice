import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: () => import("../views/HomeView.vue") },
    { path: "/tts", name: "tts", component: () => import("../views/TtsView.vue") },
    { path: "/login", name: "login", component: () => import("../views/LoginView.vue") },
    { path: "/courseware", name: "courseware-library", component: () => import("../views/CoursewareLibraryView.vue") },
    { path: "/courseware/new", name: "courseware-new", component: () => import("../views/CoursewareView.vue") },
    { path: "/courseware/:id", name: "courseware-edit", component: () => import("../views/CoursewareView.vue") },
  ],
});

export default router;
