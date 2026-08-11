import { createRouter, createWebHistory } from 'vue-router';
import SingleDetectionView from './views/SingleDetectionView.vue';
import BatchDetectionView from './views/BatchDetectionView.vue';
import DetectionRecordsView from './views/DetectionRecordsView.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/detections/single' },
    { path: '/detections/single', component: SingleDetectionView },
    { path: '/detections/batch', component: BatchDetectionView },
    { path: '/results', component: DetectionRecordsView },
  ],
});
