<script setup lang="ts">
import { FileSearch, History, Layers3, LayoutGrid, PanelLeftClose, PanelLeftOpen, SlidersHorizontal } from 'lucide-vue-next';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppLogo from './components/AppLogo.vue';
import DualStreamIllustration from './components/DualStreamIllustration.vue';
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
  { label: '系统概览', icon: LayoutGrid, to: '/overview' },
  { label: '单条评论检测', icon: FileSearch, to: '/detections/single' },
  { label: '批量检测任务', icon: Layers3, to: '/detections/batch' },
  { label: '检测记录', icon: History, to: '/results' },
  { label: '模型与设置', icon: SlidersHorizontal, to: '/settings' },
];
// 结果详情页归属"检测记录"
const isActive = (to: string) => route.path === to || route.path.startsWith(`${to}/`);

// 路由变化时重新读取，登录后无需刷新即可显示用户
const session = computed(() => {
  void route.fullPath;
  return getSession();
});
const roleLabel = computed(() => (session.value?.role === 'admin' ? '系统管理员' : '审核员'));
</script>

<template>
  <div v-if="isAuthLayout" class="auth-shell">
    <header class="auth-header">
      <div class="auth-brand"><AppLogo /><span class="version">{{ APP_VERSION }}</span></div>
      <div class="auth-intro">
        <h1>{{ APP_NAME }}</h1>
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
    <aside class="side">
      <div class="brand">
        <AppLogo />
        <div class="brand-text fade"><strong>{{ APP_NAME }}</strong><span class="version">{{ APP_VERSION }}</span></div>
      </div>

      <nav class="side-nav" aria-label="主导航">
        <RouterLink
          v-for="item in navigation" :key="item.to" :to="item.to"
          :class="{ active: isActive(item.to) }" :title="sidebarCollapsed ? item.label : undefined"
        >
          <component :is="item.icon" :size="17" :stroke-width="1.8" />
          <span class="fade">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="side-foot">
        <button
          type="button" class="side-toggle"
          :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'" :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          :aria-expanded="!sidebarCollapsed" @click="toggleSidebar"
        >
          <PanelLeftOpen v-if="sidebarCollapsed" :size="17" :stroke-width="1.8" />
          <PanelLeftClose v-else :size="17" :stroke-width="1.8" />
          <span class="fade">{{ sidebarCollapsed ? '展开侧边栏' : '收起侧边栏' }}</span>
        </button>
        <div v-if="session" class="me">
          <b class="avatar">{{ session.username.slice(0, 1).toUpperCase() }}</b>
          <div class="me-text fade">{{ session.username }}<small>{{ roleLabel }}</small></div>
        </div>
      </div>
    </aside>

    <main class="main">
      <RouterView :key="route.fullPath" />
    </main>
  </div>
</template>

<style scoped>
.auth-shell { display: grid; grid-template-columns: minmax(420px, 1fr) minmax(400px, 1fr); min-height: 100vh; background: var(--color-bg); }
.auth-header { display: flex; flex-direction: column; gap: 28px; padding: 44px 56px; background: var(--color-brand-deep); color: #fff; }
.auth-brand { display: flex; align-items: center; gap: 10px; }
.auth-brand :deep(.app-logo) { background: rgb(255 255 255 / 10%); }
.auth-intro { margin-top: auto; }
.auth-intro h1 { max-width: 520px; margin: 0; font-size: 30px; line-height: 1.4; text-wrap: balance; }
.auth-intro p { max-width: 480px; margin: 14px 0 0; color: rgb(255 255 255 / 72%); font-size: 14px; line-height: 1.8; }
.auth-foot { margin-top: auto; color: rgb(255 255 255 / 55%); font-size: 12px; }
.auth-main { display: grid; place-items: center; padding: 40px 24px; }

.shell { display: grid; grid-template-columns: 232px minmax(0, 1fr); min-height: 100vh; transition: grid-template-columns .2s ease; }
.shell.collapsed { grid-template-columns: 72px minmax(0, 1fr); }
/* 收起/展开只改变侧栏宽度：图标位置两种状态完全一致，文字区域固定宽度不重排，被裁切后淡出 */
.side { position: sticky; top: 0; display: flex; height: 100vh; flex-direction: column; padding: 18px 14px; overflow: hidden; background: var(--color-sidebar); }
.fade { transition: opacity .2s ease .12s; }
.collapsed .fade { opacity: 0; transition: opacity .1s ease; pointer-events: none; }

.brand { display: flex; align-items: flex-start; gap: 10px; padding: 4px 5px 18px; border-bottom: 1px solid var(--color-sidebar-line); }
.brand-text { flex: none; width: 148px; }
.brand-text strong { display: block; font-size: 13px; line-height: 1.45; text-wrap: balance; }
.version { display: inline-block; margin-top: 4px; padding: 0 6px; border-radius: 4px; background: var(--color-surface); color: var(--color-primary); font-size: 11px; font-weight: 600; }
.auth-brand .version { margin-top: 0; background: var(--color-accent); color: var(--color-on-accent); }

.side-nav { display: flex; flex-direction: column; gap: 2px; margin-top: 14px; }
.side-nav a, .side-toggle { display: flex; align-items: center; gap: 10px; width: 100%; padding: 9px 13px; border: 0; border-radius: 10px; background: transparent; color: var(--color-text-secondary); font: inherit; font-size: 14px; text-align: left; text-decoration: none; white-space: nowrap; }
.side-nav a svg, .side-toggle svg { flex: none; opacity: .75; }
.side-nav a:hover, .side-toggle:hover { background: color-mix(in srgb, var(--color-surface) 55%, transparent); }
.side-nav a.active { background: var(--color-surface); box-shadow: var(--shadow-raised); color: var(--color-primary); font-weight: 600; }
.side-nav a.active svg { color: var(--color-behavior); opacity: 1; }

.side-foot { display: flex; flex-direction: column; gap: 6px; margin-top: auto; }
.side-toggle { color: var(--color-text-muted); }
.me { display: flex; align-items: center; gap: 10px; min-width: 0; padding: 7px; border-radius: 10px; background: var(--color-surface); font-size: 13px; }
.avatar { display: grid; flex: none; width: 30px; height: 30px; place-items: center; border-radius: 50%; background: var(--color-accent); color: var(--color-on-accent); font-size: 12px; }
.me-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.me-text small { display: block; color: var(--color-text-muted); font-size: 12px; }

.main { min-width: 0; }

@media (max-width: 760px) {
  .auth-shell { grid-template-columns: 1fr; }
  .auth-header { padding: 28px 24px; }
  .shell, .shell.collapsed { display: block; }
  .side { position: static; height: auto; }
  .side-nav { flex-direction: row; overflow-x: auto; }
  .side-foot { display: none; }
}
</style>
