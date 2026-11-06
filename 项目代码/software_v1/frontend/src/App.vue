<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppLogo from './components/AppLogo.vue';
import DualStreamIllustration from './components/DualStreamIllustration.vue';
import AppHeader from './components/layout/AppHeader.vue';
import AppSidebar from './components/layout/AppSidebar.vue';
import AppTabs from './components/layout/AppTabs.vue';
import { getDetectionRecords } from './api/client';
import { getSession } from './auth';
import { APP_NAME, APP_VERSION } from './brand';

const route = useRoute();
const router = useRouter();
const isAuthLayout = computed(() => route.meta.layout === 'auth');
const SIDEBAR_COLLAPSED_KEY = 'review-monitoring.sidebar-collapsed';
const sidebarCollapsed = ref(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true');
function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(sidebarCollapsed.value));
}
function onAuthExpired() { void router.replace({ path: '/login', query: { redirect: route.fullPath } }); }
onMounted(() => window.addEventListener('auth:expired', onAuthExpired));
onBeforeUnmount(() => window.removeEventListener('auth:expired', onAuthExpired));

// 路由变化时重新读取，登录后无需刷新即可显示用户
const session = computed(() => {
  void route.fullPath;
  return getSession();
});

// 侧栏"待复核队列"的角标：处置建议为人工复核的结果总数，切换页面时刷新
const reviewCount = ref<number | null>(null);
async function loadReviewCount() {
  if (isAuthLayout.value || !session.value) return;
  try {
    reviewCount.value = (await getDetectionRecords({ page: 1, page_size: 1, action: 'review' })).total;
  } catch {
    reviewCount.value = null;
  }
}
watch(() => route.path, loadReviewCount, { immediate: true });

// 标签页栏的"刷新当前页"：改变 key 让当前页面重新挂载、重新请求数据
const reloadCount = ref(0);
</script>

<template>
  <div v-if="isAuthLayout" class="auth-shell">
    <header class="auth-header">
      <div class="auth-brand"><AppLogo /><span>{{ APP_NAME }}</span></div>
      <div class="auth-intro">
        <h1>{{ APP_NAME }}<span class="version">{{ APP_VERSION }}</span></h1>
        <p>评论文本经 ALBERT 语义编码、用户行为经 GRU 时序编码，两路证据由自适应门控融合，给出辅助审核建议。</p>
      </div>
      <DualStreamIllustration />
      <small class="auth-foot">检测结果仅作为辅助审核建议，不替代人工事实认定。</small>
    </header>
    <main class="auth-main">
      <RouterView :key="route.fullPath" />
    </main>
  </div>

  <div v-else class="shell" :class="{ collapsed: sidebarCollapsed }">
    <AppSidebar :collapsed="sidebarCollapsed" :review-count="reviewCount" :is-admin="session?.role === 'admin'" />
    <div class="workspace">
      <div class="workspace-head">
        <AppHeader :collapsed="sidebarCollapsed" @toggle="toggleSidebar" />
        <AppTabs @refresh="reloadCount++" />
      </div>
      <main class="main">
        <RouterView :key="`${route.fullPath}:${reloadCount}`" />
      </main>
    </div>
  </div>
</template>

<style scoped>
/* 登录页：左侧品牌区（主色渐变 + 插图），右侧登录卡片 */
.auth-shell { display: grid; grid-template-columns: minmax(420px, 1fr) minmax(400px, 1fr); min-height: 100vh; background: var(--color-bg); }
.auth-header { position: relative; display: flex; flex-direction: column; gap: 28px; padding: 40px 56px; overflow: hidden; background: radial-gradient(circle at 85% 15%, rgb(255 255 255 / 14%), transparent 40%), linear-gradient(150deg, var(--color-primary-hover), var(--color-primary-active)); color: #fff; }
.auth-brand { display: flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 500; }
.auth-brand :deep(.app-logo) { background: rgb(255 255 255 / 16%); }
.auth-intro { margin-top: auto; }
.auth-intro h1 { margin: 0; font-size: 25px; font-weight: 600; line-height: 1.45; }
.auth-intro .version { margin-left: 10px; padding: 2px 8px; border-radius: 4px; background: rgb(255 255 255 / 20%); color: #fff; font-size: 13px; vertical-align: 5px; }
.auth-intro p { max-width: 480px; margin: 14px 0 0; color: rgb(255 255 255 / 80%); font-size: 14px; line-height: 1.8; }
.auth-foot { margin-top: auto; color: rgb(255 255 255 / 60%); font-size: 12px; }
.auth-main { display: grid; place-items: center; padding: 40px 24px; }

/* 工作台：侧栏占满左侧，右边是顶栏 + 标签页栏（吸顶）+ 内容区 */
.shell { display: flex; min-height: 100vh; }
.workspace { display: flex; min-width: 0; flex: 1; flex-direction: column; }
.workspace-head { position: sticky; top: 0; z-index: 15; }
.main { min-width: 0; flex: 1; }

@media (max-width: 760px) {
  .auth-shell { grid-template-columns: 1fr; }
  .auth-header { padding: 28px 24px; }
  .shell { display: block; }
}
</style>
