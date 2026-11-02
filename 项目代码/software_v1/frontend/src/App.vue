<script setup lang="ts">
import {
  Activity,
  ClipboardCheck,
  FileClock,
  FileSearch,
  Layers3,
  PanelLeftClose,
  PanelLeftOpen,
  Settings2,
  ShieldCheck,
} from 'lucide-vue-next';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

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
  { label: '检测预览', icon: Activity, to: '/overview' },
  { label: '单条评论检测', icon: FileSearch, to: '/detections/single' },
  { label: '批量检测任务', icon: Layers3, to: '/detections/batch' },
  { label: '检测记录', icon: FileClock, to: '/results', active: 'records' },
  { label: '结果与分析', icon: ClipboardCheck, to: '/results?mode=evidence', active: 'detail' },
  { label: '设置', icon: Settings2, to: '/settings' },
];

function isNavigationActive(item: { to?: string; active?: string }) {
  if (item.active === 'records') return route.path === '/results' && route.query.mode !== 'evidence';
  if (item.active === 'detail') return route.path.startsWith('/results/') || (route.path === '/results' && route.query.mode === 'evidence');
  return item.to === route.path;
}
</script>

<template>
  <div v-if="isAuthLayout" class="auth-shell">
    <header class="auth-header">
      <div class="auth-brand">
        <span class="brand-mark"><ShieldCheck :size="22" /></span>
        <span class="auth-brand-copy">
          <strong>全域电商异常评论监测平台</strong>
        </span>
      </div>
      <span class="auth-context">内部审核平台</span>
    </header>
    <main class="auth-main">
      <RouterView :key="route.fullPath" />
    </main>
  </div>

  <div v-else class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark"><ShieldCheck :size="22" /></span>
        <span class="brand-copy">
          <strong>全域电商异常评论监测平台</strong>
        </span>
        <button
          type="button"
          class="sidebar-toggle"
          :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          :aria-expanded="!sidebarCollapsed"
          @click="toggleSidebar"
        >
          <PanelLeftOpen v-if="sidebarCollapsed" :size="17" />
          <PanelLeftClose v-else :size="17" />
        </button>
      </div>

      <nav class="navigation" aria-label="主导航">
        <component
          :is="item.to ? 'RouterLink' : 'span'"
          v-for="item in navigation"
          :key="item.label"
          :to="item.to"
          class="nav-item"
          :class="{ active: isNavigationActive(item), disabled: !item.to }"
          :aria-disabled="!item.to"
          :title="sidebarCollapsed ? item.label : undefined"
        >
          <component :is="item.icon" :size="18" />
          <span>{{ item.label }}</span>
          <small v-if="!item.to">待开发</small>
        </component>
      </nav>

      <div class="sidebar-foot">
        <div><strong>服务端接口</strong><small>FastAPI</small></div>
      </div>
    </aside>

    <main class="main-area">
      <header class="topbar">
        <div>
          <strong>全域电商异常评论监测平台</strong>
          <span>语义与时序行为融合审核</span>
        </div>
      </header>
      <RouterView :key="route.fullPath" />
    </main>
  </div>
</template>
