<script setup lang="ts">
import { ClipboardCheck, FileSearch, History, Layers3, LayoutDashboard, PanelLeftClose, PanelLeftOpen, SlidersHorizontal } from 'lucide-vue-next';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppLogo from './components/AppLogo.vue';
import DualStreamIllustration from './components/DualStreamIllustration.vue';
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

const navigation = [
  { group: '工作台', items: [
    { label: '系统概览', icon: LayoutDashboard, to: '/overview' },
    { label: '待复核队列', icon: ClipboardCheck, to: '/review', badge: true },
    { label: '检测记录', icon: History, to: '/results' },
  ] },
  { group: '发起检测', items: [
    { label: '单条评论检测', icon: FileSearch, to: '/detections/single' },
    { label: '批量检测任务', icon: Layers3, to: '/detections/batch' },
  ] },
  { group: '系统管理', items: [
    { label: '模型与设置', icon: SlidersHorizontal, to: '/settings' },
  ] },
];
// 结果详情页归属"检测记录"
const isActive = (to: string) => route.path === to || route.path.startsWith(`${to}/`);

// 路由变化时重新读取，登录后无需刷新即可显示用户
const session = computed(() => {
  void route.fullPath;
  return getSession();
});
const roleLabel = computed(() => (session.value?.role === 'admin' ? '系统管理员' : '审核员'));

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
    <header class="topbar">
      <RouterLink to="/overview" class="brand">
        <AppLogo />
        <strong>{{ APP_NAME }}</strong>
        <span class="version">{{ APP_VERSION }}</span>
      </RouterLink>
      <RouterLink v-if="session" to="/settings#account" class="me" title="账户与安全">
        <b class="avatar">{{ session.username.slice(0, 1).toUpperCase() }}</b>
        <span class="me-text">{{ session.username }}<small>{{ roleLabel }}</small></span>
      </RouterLink>
    </header>

    <aside class="side">
      <nav class="side-nav" aria-label="主导航">
        <template v-for="section in navigation" :key="section.group">
          <p class="nav-group fade">{{ section.group }}</p>
          <RouterLink
            v-for="item in section.items" :key="item.to" :to="item.to"
            :class="{ active: isActive(item.to) }" :title="sidebarCollapsed ? item.label : undefined"
          >
            <component :is="item.icon" :size="18" :stroke-width="1.8" />
            <span class="fade">{{ item.label }}</span>
            <em v-if="item.badge && reviewCount" class="nav-badge num">{{ reviewCount > 99 ? '99+' : reviewCount }}</em>
          </RouterLink>
        </template>
      </nav>

      <div class="side-foot">
        <button
          type="button" class="side-toggle"
          :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'" :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          :aria-expanded="!sidebarCollapsed" @click="toggleSidebar"
        >
          <PanelLeftOpen v-if="sidebarCollapsed" :size="18" :stroke-width="1.8" />
          <PanelLeftClose v-else :size="18" :stroke-width="1.8" />
        </button>
      </div>
    </aside>

    <main class="main">
      <RouterView :key="route.fullPath" />
    </main>
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

/* 工作台：顶栏通栏，下面是侧栏 + 内容区 */
.shell { display: grid; grid-template-areas: "top top" "side main"; grid-template-columns: 220px minmax(0, 1fr); grid-template-rows: var(--header-height) 1fr; min-height: 100vh; transition: grid-template-columns .2s ease; }
.shell.collapsed { grid-template-columns: 64px minmax(0, 1fr); }

.topbar { position: sticky; top: 0; z-index: 10; display: flex; grid-area: top; align-items: center; justify-content: space-between; gap: 16px; padding: 0 20px; border-bottom: 1px solid var(--color-line); background: var(--color-surface); }
.brand { display: flex; min-width: 0; align-items: center; gap: 10px; color: var(--color-text); text-decoration: none; }
.brand strong { overflow: hidden; font-size: 16px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.version { flex: none; padding: 0 6px; border-radius: 4px; background: var(--color-primary-soft); color: var(--color-primary); font-size: 12px; font-weight: 500; line-height: 20px; }
.me { display: flex; flex: none; align-items: center; gap: 10px; padding: 4px 8px; border-radius: var(--radius-control); color: var(--color-text); text-decoration: none; }
.me:hover { background: var(--color-surface-muted); }
.avatar { display: grid; flex: none; width: 32px; height: 32px; place-items: center; border-radius: 50%; background: var(--color-primary); color: var(--color-on-primary); font-size: 13px; }
.me-text { font-size: 14px; line-height: 18px; }
.me-text small { display: block; color: var(--color-text-muted); font-size: 12px; }

/* 侧栏：白底，选中项浅主色底 + 主色字。收起/展开只改宽度，图标位置不变，文字淡出 */
.side { position: sticky; top: var(--header-height); display: flex; grid-area: side; height: calc(100vh - var(--header-height)); flex-direction: column; padding: 8px; overflow: hidden; border-right: 1px solid var(--color-line); background: var(--color-surface); }
.fade { transition: opacity .2s ease .1s; }
.collapsed .fade { opacity: 0; transition: opacity .1s ease; pointer-events: none; }
.side-nav { display: flex; flex-direction: column; gap: 4px; overflow-y: auto; }
.nav-group { margin: 12px 0 4px; padding: 0 12px; color: var(--color-text-muted); font-size: 12px; white-space: nowrap; }
.nav-group:first-child { margin-top: 4px; }
.side-nav a { position: relative; display: flex; align-items: center; gap: 12px; height: 40px; padding: 0 12px 0 15px; border-radius: var(--radius-control); color: var(--color-text-secondary); font-size: 14px; text-decoration: none; white-space: nowrap; }
.side-nav a svg { flex: none; }
.side-nav a:hover { background: var(--color-surface-muted); color: var(--color-text); }
.side-nav a.active { background: var(--color-primary-soft); color: var(--color-primary); font-weight: 500; }
.nav-badge { min-width: 20px; margin-left: auto; padding: 0 6px; border-radius: 10px; background: var(--color-fake); color: #fff; font-size: 12px; font-style: normal; line-height: 18px; text-align: center; }
.collapsed .nav-badge { position: absolute; top: 5px; left: 30px; min-width: 8px; height: 8px; padding: 0; overflow: hidden; color: transparent; }
.side-foot { margin-top: auto; padding-top: 8px; border-top: 1px solid var(--color-line); }
.side-toggle { display: grid; width: 40px; height: 32px; margin-left: 4px; place-items: center; border: 0; border-radius: var(--radius-control); background: transparent; color: var(--color-text-muted); }
.side-toggle:hover { background: var(--color-surface-muted); color: var(--color-text); }

.main { grid-area: main; min-width: 0; }

@media (max-width: 760px) {
  .auth-shell { grid-template-columns: 1fr; }
  .auth-header { padding: 28px 24px; }
  .shell, .shell.collapsed { display: block; }
  .brand strong { font-size: 14px; }
  .me-text { display: none; }
  .side { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--color-line); }
  .side-nav { flex-direction: row; }
  .nav-group, .side-foot { display: none; }
}
</style>
