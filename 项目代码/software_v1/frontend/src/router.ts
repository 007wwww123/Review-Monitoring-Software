import { createRouter, createWebHistory } from 'vue-router';
import SingleDetectionView from './views/SingleDetectionView.vue';
import BatchDetectionView from './views/BatchDetectionView.vue';
import DetectionRecordsView from './views/DetectionRecordsView.vue';
import LoginView from './views/LoginView.vue';
import DetectionResultDetailView from './views/DetectionResultDetailView.vue';
import { isAuthenticated } from './auth';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/', redirect: '/detections/single' },
    { path: '/detections/single', component: SingleDetectionView },
    { path: '/detections/batch', component: BatchDetectionView },
    { path: '/results', component: DetectionRecordsView },
    { path: '/results/:resultId(\\d+)', component: DetectionResultDetailView },
  ],
});

router.beforeEach((to) => {
  if (to.meta.public || isAuthenticated()) return true;
  return { path: '/login', query: { redirect: to.fullPath } };
});
