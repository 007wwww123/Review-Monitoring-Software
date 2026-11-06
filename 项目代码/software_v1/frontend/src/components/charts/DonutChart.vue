<script setup lang="ts">
// 环形图：按顺序画出各段占比，中间显示一行大字和一行说明
import { computed } from 'vue';
import { arcPath } from './geometry';

export type DonutTone = 'primary' | 'behavior' | 'fake' | 'warn' | 'success' | 'cyan' | 'neutral';
const props = defineProps<{ parts: { key: string; label: string; value: number; tone: DonutTone }[]; center: string; caption: string }>();

const CX = 150, CY = 84, R = 64, GAP = 0.025;
const segments = computed(() => {
  const total = props.parts.reduce((sum, part) => sum + Math.max(part.value, 0), 0);
  if (!total) return [];
  const visible = props.parts.filter((part) => part.value > 0);
  // 多段时每段之间留一道细缝；只有一段时画整圈（终点与起点重合画不出来，留极小的缝）
  const gap = visible.length > 1 ? GAP : 0;
  let angle = -Math.PI / 2;
  return visible.map((part) => {
    const sweep = (2 * Math.PI * part.value) / total;
    const start = angle + gap / 2;
    const end = visible.length === 1 ? angle + 2 * Math.PI - 0.0001 : Math.max(angle + sweep - gap / 2, start + 0.001);
    const path = arcPath(CX, CY, R, start, end);
    angle += sweep;
    return { key: part.key, tone: part.tone, path };
  });
});
</script>

<template>
  <svg class="donut" viewBox="0 0 300 168" role="img" :aria-label="`${caption} ${center}`">
    <circle class="track" :cx="CX" :cy="CY" :r="R" />
    <path v-for="segment in segments" :key="segment.key" :class="segment.tone" :d="segment.path" />
    <text class="figure" :class="{ long: center.length > 6 }" :x="CX" :y="CY + 2" text-anchor="middle">{{ center }}</text>
    <text class="caption" :x="CX" :y="CY + 22" text-anchor="middle">{{ caption }}</text>
  </svg>
</template>

<style scoped>
.donut { display: block; width: 100%; max-width: 300px; margin: 0 auto; }
.track, path { fill: none; stroke-width: 18; }
.track { stroke: var(--color-track); }
.primary { stroke: var(--color-primary); }
.behavior { stroke: var(--color-behavior); }
.fake { stroke: var(--color-fake); }
.warn { stroke: var(--color-warn); }
.success { stroke: var(--color-success); }
.cyan { stroke: var(--color-cyan); }
.neutral { stroke: var(--color-line-strong); }
.figure { fill: var(--color-text); font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums; }
.figure.long { font-size: 16px; }
.caption { fill: var(--color-text-muted); font-size: 12px; }
</style>
