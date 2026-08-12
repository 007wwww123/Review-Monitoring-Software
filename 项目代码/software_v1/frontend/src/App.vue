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
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();
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
  { label: '系统概览', icon: Activity, to: '/overview' },
  { label: '单条评论检测', icon: FileSearch, to: '/detections/single' },
  { label: '批量检测任务', icon: Layers3, to: '/detections/batch' },
  { label: '检测记录', icon: FileClock, to: '/results', active: 'records' },
  { label: '结果与证据', icon: ClipboardCheck, to: '/results?mode=evidence', active: 'detail' },
  { label: '系统设置', icon: Settings2, to: '/settings' },
];

function isNavigationActive(item: { to?: string; active?: string }) {
  if (item.active === 'records') return route.path === '/results' && route.query.mode !== 'evidence';
  if (item.active === 'detail') return route.path.startsWith('/results/') || (route.path === '/results' && route.query.mode === 'evidence');
  return item.to === route.path;
}
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark"><ShieldCheck :size="22" /></span>
        <span class="brand-copy">
          <strong>评论风控台</strong>
          <small>V1.0.0 开发版</small>
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
        <span class="service-dot"></span>
        <div><strong>模拟服务在线</strong><small>MSW 开发环境</small></div>
      </div>
    </aside>

    <main class="main-area">
      <header class="topbar">
        <div>
          <strong>虚假评论智能检测系统</strong>
          <span>语义与时序行为融合审核</span>
        </div>
        <span class="environment-badge">开发环境</span>
      </header>
      <RouterView :key="route.fullPath" />
    </main>
  </div>
</template>
