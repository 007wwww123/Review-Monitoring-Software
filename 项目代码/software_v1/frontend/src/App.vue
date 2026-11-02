<script setup lang="ts">
import { FileSearch, History, Layers3, LayoutGrid, PanelLeftClose, PanelLeftOpen, SlidersHorizontal } from 'lucide-vue-next';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppLogo from './components/AppLogo.vue';
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
      <div class="auth-brand"><AppLogo /><strong>{{ APP_NAME }}</strong><span class="version">{{ APP_VERSION }}</span></div>
    </header>
    <main class="auth-main">
      <RouterView :key="route.fullPath" />
    </main>
  </div>

  <div v-else class="shell" :class="{ collapsed: sidebarCollapsed }">
    <aside class="side">
      <div class="brand">
        <AppLogo />
        <div class="brand-text"><strong>{{ APP_NAME }}</strong><span class="version">{{ APP_VERSION }}</span></div>
      </div>

      <nav class="side-nav" aria-label="主导航">
        <RouterLink
          v-for="item in navigation" :key="item.to" :to="item.to"
          :class="{ active: isActive(item.to) }" :title="sidebarCollapsed ? item.label : undefined"
        >
          <component :is="item.icon" :size="17" :stroke-width="1.8" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="side-foot">
        <div v-if="session" class="me">
          <b class="avatar">{{ session.username.slice(0, 1).toUpperCase() }}</b>
          <div class="me-text">{{ session.username }}<small>{{ roleLabel }}</small></div>
        </div>
        <button
          type="button" class="side-toggle"
          :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'" :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          :aria-expanded="!sidebarCollapsed" @click="toggleSidebar"
        >
          <PanelLeftOpen v-if="sidebarCollapsed" :size="17" />
          <PanelLeftClose v-else :size="17" />
        </button>
      </div>
    </aside>

    <main class="main">
      <RouterView :key="route.fullPath" />
    </main>
  </div>
</template>

<style scoped>
.auth-brand { display: flex; align-items: center; gap: 10px; }
.auth-brand strong { font-size: 15px; }

.shell { display: grid; grid-template-columns: 232px minmax(0, 1fr); min-height: 100vh; transition: grid-template-columns .2s ease; }
.shell.collapsed { grid-template-columns: 72px minmax(0, 1fr); }
.side { position: sticky; top: 0; display: flex; height: 100vh; flex-direction: column; padding: 18px 14px; background: var(--color-sidebar); }

.brand { display: flex; align-items: flex-start; gap: 10px; padding: 4px 6px 18px; border-bottom: 1px solid #dde0ec; }
.brand-text strong { display: block; font-size: 13px; line-height: 1.45; text-wrap: balance; }
.version { display: inline-block; margin-top: 4px; padding: 0 6px; border-radius: 4px; background: var(--color-surface); color: var(--color-primary); font-size: 11px; font-weight: 600; }
.auth-brand .version { margin-top: 0; background: var(--color-primary-soft); }

.side-nav { display: flex; flex-direction: column; gap: 2px; margin-top: 14px; }
.side-nav a { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 10px; color: var(--color-text-secondary); text-decoration: none; white-space: nowrap; }
.side-nav a svg { flex: none; opacity: .75; }
.side-nav a:hover { background: rgb(255 255 255 / 55%); }
.side-nav a.active { background: var(--color-surface); box-shadow: 0 1px 2px rgb(22 26 51 / 8%), 0 0 0 1px rgb(22 26 51 / 4%); color: var(--color-primary); font-weight: 600; }
.side-nav a.active svg { color: var(--color-behavior); opacity: 1; }

.side-foot { display: flex; align-items: center; gap: 6px; margin-top: auto; }
.me { display: flex; flex: 1; align-items: center; gap: 10px; min-width: 0; padding: 10px; border-radius: 10px; background: var(--color-surface); font-size: 13px; }
.avatar { display: grid; flex: none; width: 30px; height: 30px; place-items: center; border-radius: 50%; background: var(--color-accent); color: var(--color-primary); font-size: 12px; }
.me-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.me-text small { display: block; color: var(--color-text-muted); font-size: 12px; }
.side-toggle { display: grid; flex: none; width: 30px; height: 30px; place-items: center; padding: 0; border: 0; border-radius: 8px; background: transparent; color: var(--color-text-muted); }
.side-toggle:hover { background: var(--color-surface); color: var(--color-primary); }

.collapsed .side { padding-right: 10px; padding-left: 10px; }
.collapsed .brand { justify-content: center; padding-right: 0; padding-left: 0; }
.collapsed .brand-text, .collapsed .side-nav a span, .collapsed .me-text { display: none; }
.collapsed .side-nav a { justify-content: center; padding: 10px 0; }
.collapsed .side-foot { flex-direction: column; }
.collapsed .me { justify-content: center; padding: 6px; background: transparent; }

.main { min-width: 0; }

@media (max-width: 760px) {
  .shell, .shell.collapsed { display: block; }
  .side { position: static; height: auto; }
  .side-nav { flex-direction: row; overflow-x: auto; }
  .side-foot { display: none; }
}
</style>
