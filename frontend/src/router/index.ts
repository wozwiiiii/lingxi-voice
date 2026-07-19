import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: () => import("../views/HomeView.vue") },
    { path: "/tts", name: "tts", component: () => import("../views/TtsView.vue") },
    { path: "/login", name: "login", component: () => import("../views/LoginView.vue") },
  ],
});

export default router;
