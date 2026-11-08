<script setup lang="ts">
// 页头卡片：图标块（或 icon 插槽）+ 标题与说明（左）+ 关键数字或操作（右）；extra 插槽放在下方通栏
import type { Component } from 'vue';

defineProps<{ title: string; desc?: string; icon?: Component }>();
</script>

<template>
  <header class="page-title page-head">
    <div v-if="icon || $slots.icon" class="page-icon"><slot name="icon"><component :is="icon" :size="24" :stroke-width="1.8" /></slot></div>
    <div class="page-head-main">
      <div class="page-head-title"><h1>{{ title }}</h1><slot name="title-extra" /></div>
      <p class="page-id"><slot name="desc">{{ desc }}</slot></p>
    </div>
    <div v-if="$slots.actions" class="page-actions"><slot name="actions" /></div>
    <div v-if="$slots.extra" class="page-head-extra"><slot name="extra" /></div>
  </header>
</template>

<style scoped>
/* 右上角一片很淡的主色光晕，让页头和普通内容卡片区分开 */
.page-head { position: relative; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; column-gap: 16px; margin: 0 0 16px; padding: 20px 24px; overflow: hidden; border-radius: var(--radius-card); background: radial-gradient(520px 180px at 100% 0, var(--color-primary-soft), transparent 72%), var(--color-surface); }
.page-head:not(:has(.page-icon)) { grid-template-columns: minmax(0, 1fr) auto; }
.page-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 12px; background: var(--color-primary-soft); color: var(--color-primary); }
.page-head-main { min-width: 0; }
.page-head-title { display: flex; align-items: center; gap: 10px; }
h1 { margin: 0; font-size: 20px; font-weight: 600; line-height: 28px; }
.page-id { margin: 4px 0 0; color: var(--color-text-muted); font-size: 13px; line-height: 20px; }
.page-actions { display: flex; align-items: center; gap: 8px; }
.page-head-extra { grid-column: 1 / -1; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--color-line); }

@media (max-width: 860px) {
  .page-head, .page-head:not(:has(.page-icon)) { grid-template-columns: auto minmax(0, 1fr); row-gap: 14px; padding: 16px; }
  .page-actions { grid-column: 1 / -1; flex-wrap: wrap; }
}
</style>
