<script setup lang="ts">
// 雷达图：语义四分类的相对匹配度，selected 为当前判定类型
import { computed } from 'vue';
import { percent } from '../../labels';
import { polar } from './geometry';

const props = defineProps<{ items: { key: string; label: string; value: number }[]; selected?: string }>();

const CX = 150, CY = 122, R = 78;
const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / props.items.length;
// 外圈刻度按最大值向上取到 0.25 的倍数，避免小分数挤在中心
const scale = computed(() => Math.max(0.25, Math.ceil(Math.max(...props.items.map((item) => item.value)) * 4) / 4));
const rings = computed(() => [0.25, 0.5, 0.75, 1].map((k) => props.items.map((_, i) => polar(CX, CY, R * k, angle(i)).join(',')).join(' ')));
const axes = computed(() => props.items.map((_, i) => polar(CX, CY, R, angle(i))));
const points = computed(() => props.items.map((item, i) => polar(CX, CY, (R * item.value) / scale.value, angle(i))));
const labels = computed(() => props.items.map((item, i) => {
  const [x, y] = polar(CX, CY, R + 24, angle(i));
  return { ...item, x, y: y + (Math.sin(angle(i)) > 0.5 ? 6 : Math.sin(angle(i)) < -0.5 ? -6 : 0) };
}));
</script>

<template>
  <svg class="radar" viewBox="0 0 300 250" role="img" aria-label="语义相对匹配度雷达图">
    <polygon v-for="(ring, i) in rings" :key="i" class="ring" :points="ring" />
    <line v-for="(axis, i) in axes" :key="`a${i}`" class="axis" :x1="CX" :y1="CY" :x2="axis[0]" :y2="axis[1]" />
    <polygon class="area" :points="points.map((p) => p.join(',')).join(' ')" />
    <circle
      v-for="(p, i) in points" :key="`p${i}`" :cx="p[0]" :cy="p[1]"
      :r="items[i].key === selected ? 6 : 3.5" :class="items[i].key === selected ? 'dot selected' : 'dot'"
    />
    <g v-for="item in labels" :key="item.key" :class="{ selected: item.key === selected }" class="label">
      <text :x="item.x" :y="item.y - 2" text-anchor="middle">{{ item.label }}</text>
      <text class="value" :x="item.x" :y="item.y + 13" text-anchor="middle">{{ percent(item.value) }}</text>
    </g>
  </svg>
</template>

<style scoped>
.radar { display: block; width: 100%; max-width: 320px; margin: 0 auto; }
.ring, .axis { fill: none; stroke: var(--color-line); }
.area { fill: var(--color-primary); fill-opacity: .12; stroke: var(--color-primary); stroke-width: 2; stroke-linejoin: round; }
.dot { fill: var(--color-primary); }
.dot.selected { fill: var(--color-accent); stroke: var(--color-primary); stroke-width: 2; }
.label text { fill: var(--color-text-muted); font-size: 12px; }
.label .value { fill: var(--color-text); font-size: 11px; font-variant-numeric: tabular-nums; }
.label.selected text:first-child { fill: var(--color-primary); font-weight: 700; }
</style>
