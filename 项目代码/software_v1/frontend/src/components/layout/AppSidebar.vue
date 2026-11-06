<script setup lang="ts">
// 侧栏：顶部品牌区 + 可折叠的分组菜单（同一时间只展开一组）。
// 收起时只显示图标：分组标题隐藏，各组菜单项平铺，组与组之间用细线分隔
import { ChevronDown } from 'lucide-vue-next';
import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import AppLogo from '../AppLogo.vue';
import { APP_NAME, APP_VERSION } from '../../brand';
import { NAVIGATION, isGroup, matchRoute, type NavEntry, type NavLeaf } from '../../navigation';

const props = defineProps<{ collapsed: boolean; reviewCount: number | null; isAdmin: boolean }>();
const route = useRoute();

const match = computed(() => matchRoute(route.path, route.hash, route.params));
const entries = computed<NavEntry[]>(() => NAVIGATION.map((entry) => isGroup(entry)
  ? { ...entry, children: entry.children.filter((leaf) => !leaf.adminOnly || props.isAdmin) }
  : entry));
const openGroup = ref<string | null>(match.value?.group?.key ?? null);
// 切换到别的分组下的页面时，自动展开那一组
watch(() => match.value?.group?.key, (key) => { if (key) openGroup.value = key; });

const isActive = (leaf: NavLeaf) => match.value?.leaf.key === leaf.key;
function toggleGroup(key: string) { openGroup.value = openGroup.value === key ? null : key; }
// 标题前半句和后半句分两行显示："基于…融合的" / "…系统"
const nameLines = computed(() => {
  const cut = APP_NAME.indexOf('的');
  return cut > 0 && cut < APP_NAME.length - 1 ? [APP_NAME.slice(0, cut + 1), APP_NAME.slice(cut + 1)] : [APP_NAME];
});
</script>

<template>
  <aside class="side" :class="{ collapsed }">
    <RouterLink to="/overview" class="brand" :title="APP_NAME">
      <AppLogo class="brand-logo" />
      <span class="brand-name fade">
        <strong :class="{ single: nameLines.length === 1 }"><span v-for="line in nameLines" :key="line">{{ line }}</span></strong>
        <em>{{ APP_VERSION }}</em>
      </span>
    </RouterLink>

    <nav class="side-nav" aria-label="主导航">
      <template v-for="entry in entries" :key="entry.key">
        <div v-if="isGroup(entry)" class="group" :class="{ open: openGroup === entry.key, 'child-active': match?.group?.key === entry.key }">
          <button type="button" class="group-head" :aria-expanded="openGroup === entry.key" @click="toggleGroup(entry.key)">
            <component :is="entry.icon" :size="20" :stroke-width="1.7" />
            <span class="fade">{{ entry.label }}</span>
            <ChevronDown class="chevron fade" :size="16" />
          </button>
          <div class="group-body">
            <div class="group-inner">
              <RouterLink
                v-for="leaf in entry.children" :key="leaf.key" :to="leaf.to" class="leaf child"
                :class="{ active: isActive(leaf) }" :title="collapsed ? leaf.label : undefined"
              >
                <component :is="leaf.icon" :size="18" :stroke-width="1.7" />
                <span class="fade">{{ leaf.label }}</span>
                <em v-if="leaf.badge && reviewCount" class="nav-badge num">{{ reviewCount > 99 ? '99+' : reviewCount }}</em>
              </RouterLink>
            </div>
          </div>
        </div>
        <RouterLink
          v-else :to="entry.to" class="leaf"
          :class="{ active: isActive(entry) }" :title="collapsed ? entry.label : undefined"
        >
          <component :is="entry.icon" :size="20" :stroke-width="1.7" />
          <span class="fade">{{ entry.label }}</span>
        </RouterLink>
      </template>
    </nav>
  </aside>
</template>

<style scoped>
.side { position: sticky; top: 0; z-index: 20; display: flex; width: 224px; height: 100vh; flex-direction: column; overflow: hidden; border-right: 1px solid var(--color-line); background: var(--color-surface); transition: width .2s ease; }
.side.collapsed { width: 64px; }
.fade { transition: opacity .2s ease .1s; }
.collapsed .fade { opacity: 0; transition: opacity .1s ease; pointer-events: none; }

/* 品牌区：Logo 在上，两行全称在下；收起后只留 Logo */
.brand { display: flex; flex: none; flex-direction: column; align-items: center; gap: 10px; padding: 20px 8px 18px; color: var(--color-primary); text-align: center; text-decoration: none; transition: padding .2s ease; }
.collapsed .brand { padding: 16px 0 12px; }
.brand-logo { width: 44px !important; height: 44px !important; border-radius: 12px !important; }
.brand-logo :deep(svg) { width: 34px; height: 34px; }
.collapsed .brand-logo { width: 36px !important; height: 36px !important; border-radius: 10px !important; }
.brand-name { width: 208px; }
.collapsed .brand-name { height: 0; overflow: hidden; }
.brand-name strong { display: flex; flex-direction: column; font-size: 14px; font-weight: 600; line-height: 21px; white-space: nowrap; }
.brand-name strong.single { font-size: 16px; line-height: 24px; }
.brand-name em { display: inline-block; margin-top: 6px; padding: 0 8px; border-radius: 4px; background: var(--color-primary-soft); font-size: 12px; font-style: normal; font-weight: 500; line-height: 20px; }

.side-nav { display: flex; flex: 1; flex-direction: column; gap: 4px; padding: 4px 8px 16px; overflow-x: hidden; overflow-y: auto; }

/* 菜单项：高 42px，图标 20px；选中为浅主色圆角底 + 主色字 */
.leaf, .group-head { position: relative; display: flex; flex: none; width: 100%; align-items: center; gap: 12px; height: 42px; padding: 0 14px; border: 0; border-radius: var(--radius-card); background: transparent; color: var(--color-text); font: inherit; font-size: 14px; text-align: left; text-decoration: none; white-space: nowrap; cursor: pointer; }
.leaf svg, .group-head svg { flex: none; }
.leaf:hover, .group-head:hover { background: var(--color-surface-muted); }
.leaf.active { background: var(--color-primary-soft); color: var(--color-primary); }
.leaf.child { padding-left: 46px; }
.leaf.child svg { color: var(--color-text-secondary); }
.leaf.child.active svg { color: var(--color-primary); }
.group.child-active > .group-head { color: var(--color-primary); }
.chevron { margin-left: auto; color: var(--color-text-muted); transition: transform .2s ease, opacity .2s ease .1s; }
.group.open .chevron { transform: rotate(180deg); }
.group.child-active .chevron { color: var(--color-primary); }

/* 分组展开动画：网格行高从 0fr 过渡到 1fr */
.group-body { display: grid; grid-template-rows: 0fr; transition: grid-template-rows .22s ease; }
.group.open .group-body { grid-template-rows: 1fr; }
.group-inner { display: flex; min-height: 0; flex-direction: column; gap: 4px; overflow: hidden; }
.group.open .group-inner { padding-top: 4px; }

.nav-badge { min-width: 20px; margin-left: auto; padding: 0 6px; border-radius: 10px; background: var(--color-fake); color: #fff; font-size: 12px; font-style: normal; line-height: 18px; text-align: center; }

/* 收起：分组标题隐藏，所有菜单项平铺成图标，组间加分隔线 */
.collapsed .group-head { display: none; }
.collapsed .group-body { grid-template-rows: 1fr; }
.collapsed .group-inner { padding-top: 0; }
.collapsed .group { margin-top: 4px; padding-top: 8px; border-top: 1px solid var(--color-line); }
.collapsed .leaf, .collapsed .leaf.child { padding-left: 14px; }
.collapsed .nav-badge { position: absolute; top: 7px; left: 30px; min-width: 8px; height: 8px; padding: 0; overflow: hidden; color: transparent; }

@media (max-width: 760px) {
  .side, .side.collapsed { position: static; width: auto; height: auto; border-right: 0; border-bottom: 1px solid var(--color-line); }
  .brand { display: none; }
  .side-nav { flex-direction: row; overflow-x: auto; }
  .group-head { display: none; }
  .group-body { grid-template-rows: 1fr; }
  .group-inner { flex-direction: row; padding-top: 0 !important; }
  .leaf.child { padding-left: 14px; }
}
</style>
