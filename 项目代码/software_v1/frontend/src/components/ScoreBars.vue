<script setup lang="ts">
// 横向分数条：按固定顺序列出各类别的相对匹配度，selected 高亮
import { percent } from '../labels';

defineProps<{ items: { key: string; label: string; value: number }[]; selected?: string; tone: 'primary' | 'behavior' }>();
</script>

<template>
  <div class="score-bars" :class="tone">
    <div v-for="item in items" :key="item.key" class="score-row" :class="{ selected: item.key === selected }">
      <span class="label">{{ item.label }}</span>
      <span class="track"><i :style="{ width: percent(item.value) }"></i></span>
      <span class="value num">{{ percent(item.value) }}</span>
    </div>
  </div>
</template>

<style scoped>
.score-row { display: grid; grid-template-columns: 84px 1fr 52px; gap: 10px; align-items: center; margin: 10px 0; font-size: 13px; }
.track { height: 8px; overflow: hidden; border-radius: 4px; background: var(--color-track); }
.track i { display: block; height: 100%; border-radius: 4px; }
.primary .track i { background: color-mix(in srgb, var(--color-primary) 35%, #fff); }
.primary .selected .track i { background: var(--color-primary); }
.behavior .track i { background: color-mix(in srgb, var(--color-behavior) 38%, #fff); }
.behavior .selected .track i { background: var(--color-behavior); }
.selected { font-weight: 600; }
.value { text-align: right; color: var(--color-text-muted); }
.selected .value { color: var(--color-text); }
</style>
