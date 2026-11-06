<script setup lang="ts">
// 标签页栏：记录打开过的页面（保存在本次会话里），可切换、关闭；右侧可刷新当前页、关闭其他标签。
// 系统概览固定在第一个，不能关闭
import { CopyX, LayoutDashboard, RotateCw, X } from 'lucide-vue-next';
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NAVIGATION, isGroup, matchRoute, type NavLeaf } from '../../navigation';

const emit = defineEmits<{ refresh: [] }>();
const route = useRoute();
const router = useRouter();
const STORAGE_KEY = 'review-monitoring.tabs';
type Tab = { key: string; to: string; title: string; leaf: string };
const HOME: Tab = { key: '/overview', to: '/overview', title: '系统概览', leaf: 'overview' };

function load(): Tab[] {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? '[]') as Tab[];
    return [HOME, ...saved.filter((tab) => tab.key !== HOME.key)];
  } catch {
    return [HOME];
  }
}
const tabs = ref<Tab[]>(load());
const leaves = NAVIGATION.flatMap((entry) => (isGroup(entry) ? entry.children : [entry])) as NavLeaf[];
const iconOf = (tab: Tab) => leaves.find((leaf) => leaf.key === tab.leaf)?.icon ?? LayoutDashboard;

// 设置页按分区各开一个标签，其余按路径
const keyOf = (path: string, hash: string) => (path === '/settings' ? `${path}${hash || '#account'}` : path);
const activeKey = computed(() => keyOf(route.path, route.hash));

watch(() => route.fullPath, () => {
  const match = matchRoute(route.path, route.hash, route.params);
  if (!match) return;
  const key = activeKey.value;
  const tab: Tab = { key, to: route.fullPath, title: match.detail ?? match.leaf.label, leaf: match.leaf.key };
  const index = tabs.value.findIndex((item) => item.key === key);
  if (index >= 0) tabs.value[index] = tab;
  else tabs.value.push(tab);
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tabs.value.slice(1)));
}, { immediate: true });

function save() { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tabs.value.slice(1))); }
function close(tab: Tab) {
  const index = tabs.value.findIndex((item) => item.key === tab.key);
  if (index <= 0) return;
  tabs.value.splice(index, 1);
  save();
  if (tab.key === activeKey.value) void router.push((tabs.value[index] ?? tabs.value[index - 1]).to);
}
function closeOthers() {
  tabs.value = tabs.value.filter((tab, index) => index === 0 || tab.key === activeKey.value);
  save();
}
</script>

<template>
  <div class="tabbar">
    <div class="tabs" role="tablist" aria-label="已打开的页面">
      <RouterLink
        v-for="(tab, index) in tabs" :key="tab.key" :to="tab.to" role="tab"
        class="tab" :class="{ active: tab.key === activeKey }" :aria-selected="tab.key === activeKey"
      >
        <component :is="iconOf(tab)" :size="15" :stroke-width="1.8" />
        <span>{{ tab.title }}</span>
        <button v-if="index > 0" type="button" class="close" :aria-label="`关闭 ${tab.title}`" @click.prevent.stop="close(tab)"><X :size="13" /></button>
      </RouterLink>
    </div>
    <div class="tab-tools">
      <button type="button" title="刷新当前页" aria-label="刷新当前页" @click="emit('refresh')"><RotateCw :size="16" :stroke-width="1.8" /></button>
      <button type="button" title="关闭其他标签" aria-label="关闭其他标签" :disabled="tabs.length <= 2" @click="closeOthers"><CopyX :size="16" :stroke-width="1.8" /></button>
    </div>
  </div>
</template>

<style scoped>
.tabbar { display: flex; height: 44px; align-items: flex-end; gap: 12px; padding: 0 12px 0 16px; border-bottom: 1px solid var(--color-line); background: var(--color-surface); }
.tabs { display: flex; min-width: 0; flex: 1; align-items: flex-end; gap: 4px; overflow-x: auto; scrollbar-width: none; }
.tab { position: relative; display: flex; flex: none; height: 36px; align-items: center; gap: 6px; padding: 0 14px; border-radius: 8px 8px 0 0; color: var(--color-text-secondary); font-size: 13px; text-decoration: none; white-space: nowrap; }
.tab:hover { background: var(--color-surface-muted); color: var(--color-text); }
.tab.active { background: var(--color-primary-soft); color: var(--color-primary); }
/* 选中标签下边的主色细线 */
.tab.active::after { position: absolute; right: 10px; bottom: 0; left: 10px; height: 2px; border-radius: 1px; background: var(--color-primary); content: ""; }
.close { display: grid; width: 18px; height: 18px; place-items: center; margin-right: -6px; border: 0; border-radius: 50%; background: transparent; color: inherit; opacity: .6; }
.close:hover { background: color-mix(in srgb, currentColor 14%, transparent); opacity: 1; }
.tab-tools { display: flex; align-self: center; gap: 2px; }
.tab-tools button { display: grid; width: 30px; height: 30px; place-items: center; border: 0; border-radius: var(--radius-control); background: transparent; color: var(--color-text-secondary); }
.tab-tools button:hover:not(:disabled) { background: var(--color-surface-muted); color: var(--color-text); }
.tab-tools button:disabled { opacity: .4; }

@media (max-width: 760px) {
  .tabbar { display: none; }
}
</style>
