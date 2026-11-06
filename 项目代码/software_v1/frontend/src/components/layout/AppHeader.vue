<script setup lang="ts">
// 顶栏：左侧收起按钮 + 面包屑；右侧检测记录搜索、明暗切换、全屏、用户下拉菜单
import { ChevronDown, KeyRound, LogOut, Maximize, Minimize, Moon, Palette, PanelLeftClose, PanelLeftOpen, Search, Sun, UserRound } from 'lucide-vue-next';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { logout } from '../../api/client';
import { clearSession, getSession } from '../../auth';
import { matchRoute } from '../../navigation';
import { applyPreferences, getPreferences } from '../../preferences';

defineProps<{ collapsed: boolean }>();
const emit = defineEmits<{ toggle: [] }>();
const route = useRoute();
const router = useRouter();

const match = computed(() => matchRoute(route.path, route.hash, route.params));
const session = computed(() => {
  void route.fullPath;
  return getSession();
});
const roleLabel = computed(() => (session.value?.role === 'admin' ? '系统管理员' : '审核员'));

// 搜索：按评论 ID、用户或商品查检测记录
const keyword = ref('');
function search() {
  const value = keyword.value.trim();
  void router.push({ path: '/results', query: value ? { keyword: value } : {} });
  keyword.value = '';
}

// 明暗切换：保存为明确的浅色或深色，其他偏好不变
const dark = ref(document.documentElement.dataset.theme === 'dark');
function toggleTheme() {
  const prefs = getPreferences();
  dark.value = !dark.value;
  applyPreferences(dark.value ? 'dark' : 'light', prefs.density, prefs.accent);
}

const fullscreen = ref(false);
function toggleFullscreen() {
  if (document.fullscreenElement) void document.exitFullscreen?.();
  else void document.documentElement.requestFullscreen?.();
}
const onFullscreenChange = () => { fullscreen.value = Boolean(document.fullscreenElement); };

// 用户下拉菜单：点击头像打开，点外面或按 Esc 关闭
const menuOpen = ref(false);
const menuRoot = ref<HTMLElement | null>(null);
const onDocClick = (event: MouseEvent) => { if (menuRoot.value && !menuRoot.value.contains(event.target as Node)) menuOpen.value = false; };
const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') menuOpen.value = false; };
function go(path: string) { menuOpen.value = false; void router.push(path); }
async function signOut() {
  menuOpen.value = false;
  try { await logout(); } catch { clearSession(); }
  await router.replace('/login');
}

onMounted(() => {
  document.addEventListener('click', onDocClick);
  document.addEventListener('keydown', onKey);
  document.addEventListener('fullscreenchange', onFullscreenChange);
});
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick);
  document.removeEventListener('keydown', onKey);
  document.removeEventListener('fullscreenchange', onFullscreenChange);
});
</script>

<template>
  <header class="topbar">
    <button
      type="button" class="icon-btn side-toggle"
      :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'" :title="collapsed ? '展开侧边栏' : '收起侧边栏'"
      :aria-expanded="!collapsed" @click="emit('toggle')"
    >
      <PanelLeftOpen v-if="collapsed" :size="19" :stroke-width="1.7" />
      <PanelLeftClose v-else :size="19" :stroke-width="1.7" />
    </button>

    <nav v-if="match" class="breadcrumb" aria-label="面包屑">
      <template v-if="match.group">
        <span class="crumb-item"><component :is="match.group.icon" :size="15" />{{ match.group.label }}</span>
        <i>/</i>
      </template>
      <RouterLink v-if="match.detail" :to="match.leaf.to" class="crumb-item"><component :is="match.leaf.icon" :size="15" />{{ match.leaf.label }}</RouterLink>
      <b v-else class="crumb-item"><component :is="match.leaf.icon" :size="15" />{{ match.leaf.label }}</b>
      <template v-if="match.detail"><i>/</i><b class="crumb-item">{{ match.detail }}</b></template>
    </nav>

    <div class="tools">
      <form class="search" role="search" @submit.prevent="search">
        <Search :size="15" />
        <input v-model="keyword" type="search" placeholder="搜索评论 ID、用户或商品" aria-label="搜索检测记录" />
      </form>
      <button type="button" class="icon-btn" :title="dark ? '切换到浅色' : '切换到深色'" :aria-label="dark ? '切换到浅色' : '切换到深色'" @click="toggleTheme">
        <Sun v-if="dark" :size="18" :stroke-width="1.7" /><Moon v-else :size="18" :stroke-width="1.7" />
      </button>
      <button type="button" class="icon-btn" :title="fullscreen ? '退出全屏' : '全屏'" :aria-label="fullscreen ? '退出全屏' : '全屏'" @click="toggleFullscreen">
        <Minimize v-if="fullscreen" :size="18" :stroke-width="1.7" /><Maximize v-else :size="18" :stroke-width="1.7" />
      </button>
      <span class="divider"></span>

      <div v-if="session" ref="menuRoot" class="user" :class="{ open: menuOpen }">
        <button type="button" class="user-trigger" :aria-expanded="menuOpen" aria-haspopup="menu" @click="menuOpen = !menuOpen">
          <b class="avatar">{{ session.username.slice(0, 1).toUpperCase() }}</b>
          <span>{{ session.username }}</span>
          <ChevronDown class="chevron" :size="16" />
        </button>
        <div v-if="menuOpen" class="user-menu" role="menu">
          <div class="user-card">
            <b class="avatar large">{{ session.username.slice(0, 1).toUpperCase() }}</b>
            <div><strong>{{ session.username }}<span class="tag ok">{{ roleLabel }}</span></strong><small>当前登录账号</small></div>
          </div>
          <button type="button" role="menuitem" @click="go('/settings#account')"><UserRound :size="16" />账户与安全</button>
          <button type="button" role="menuitem" @click="go('/settings#account')"><KeyRound :size="16" />修改密码</button>
          <button type="button" role="menuitem" @click="go('/settings#appearance')"><Palette :size="16" />界面偏好</button>
          <div class="menu-foot"><button type="button" role="menuitem" class="logout" @click="signOut"><LogOut :size="15" />退出登录</button></div>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.topbar { display: flex; height: 56px; align-items: center; gap: 12px; padding: 0 16px 0 12px; border-bottom: 1px solid var(--color-line); background: var(--color-surface); }
.icon-btn { display: grid; flex: none; width: 36px; height: 36px; place-items: center; border: 0; border-radius: var(--radius-control); background: transparent; color: var(--color-text-secondary); }
.icon-btn:hover { background: var(--color-surface-muted); color: var(--color-text); }

.breadcrumb { display: flex; min-width: 0; align-items: center; gap: 8px; color: var(--color-text-muted); font-size: 14px; white-space: nowrap; }
.breadcrumb i { color: var(--color-line-strong); font-style: normal; }
.crumb-item { display: inline-flex; align-items: center; gap: 6px; color: inherit; font-weight: 400; text-decoration: none; }
a.crumb-item:hover { color: var(--color-primary); }
b.crumb-item { color: var(--color-text); }

.tools { display: flex; align-items: center; gap: 6px; margin-left: auto; }
.search { display: flex; width: 240px; height: 34px; align-items: center; gap: 8px; margin-right: 6px; padding: 0 12px; border-radius: var(--radius-control); background: var(--color-surface-muted); color: var(--color-text-muted); }
.search:focus-within { box-shadow: 0 0 0 1px var(--color-primary) inset; background: var(--color-surface); }
.search input { width: 100%; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--color-text); font: inherit; font-size: 13px; }
.search input::placeholder { color: var(--color-placeholder); }
.divider { width: 1px; height: 20px; margin: 0 8px; background: var(--color-line); }

.user { position: relative; }
.user-trigger { display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 8px 0 4px; border: 0; border-radius: var(--radius-card); background: transparent; color: var(--color-text); font: inherit; font-size: 14px; }
.user-trigger:hover, .user.open .user-trigger { background: var(--color-primary-soft); }
.user-trigger .chevron { color: var(--color-text-muted); transition: transform .2s ease; }
.user.open .chevron { color: var(--color-primary); transform: rotate(180deg); }
.avatar { display: grid; flex: none; width: 32px; height: 32px; place-items: center; border-radius: 50%; background: var(--color-primary); color: var(--color-on-primary); font-size: 14px; }
.avatar.large { width: 44px; height: 44px; border-radius: 10px; font-size: 18px; }

.user-menu { position: absolute; top: calc(100% + 8px); right: 0; z-index: 30; width: 240px; padding: 8px; border: 1px solid var(--color-line); border-radius: 10px; background: var(--color-surface); box-shadow: var(--shadow-raised); }
.user-card { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; padding: 10px 10px 14px; border-bottom: 1px dashed var(--color-line); }
.user-card strong { display: flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 600; }
.user-card small { color: var(--color-text-muted); font-size: 12px; }
.user-menu > button { display: flex; width: 100%; height: 38px; align-items: center; gap: 10px; padding: 0 12px; border: 0; border-radius: var(--radius-control); background: transparent; color: var(--color-text); font: inherit; font-size: 14px; text-align: left; }
.user-menu > button:hover { background: var(--color-surface-muted); }
.user-menu > button svg { color: var(--color-text-secondary); }
.menu-foot { margin-top: 6px; padding: 10px 4px 2px; border-top: 1px dashed var(--color-line); text-align: center; }
.logout { display: inline-flex; height: 32px; align-items: center; gap: 6px; padding: 0 14px; border: 0; border-radius: var(--radius-control); background: var(--color-surface-muted); color: var(--color-text-secondary); font: inherit; font-size: 13px; }
.logout:hover { background: var(--color-fake-soft); color: var(--color-fake); }

@media (max-width: 960px) {
  .search { display: none; }
}
@media (max-width: 760px) {
  .breadcrumb { display: none; }
  .user-trigger span { display: none; }
}
</style>
