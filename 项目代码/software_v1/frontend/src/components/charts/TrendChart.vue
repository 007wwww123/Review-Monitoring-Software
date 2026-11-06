<script setup lang="ts">
// 按天堆叠柱状图：每根柱子下段为真实、上段为疑似虚假，柱顶显示当天总数
import { computed } from 'vue';

const props = defineProps<{ days: { key: string; label: string; fake: number; real: number }[] }>();

const W = 640, H = 236, LEFT = 36, RIGHT = 8, TOP = 20, BOTTOM = 30;
const plotW = W - LEFT - RIGHT, plotH = H - TOP - BOTTOM;
// 纵轴上限取"好看"的整数，分 4 格
const yMax = computed(() => {
  const max = Math.max(4, ...props.days.map((d) => d.fake + d.real));
  const step = Math.ceil(max / 4 / (max > 40 ? 10 : max > 20 ? 5 : 1)) * (max > 40 ? 10 : max > 20 ? 5 : 1);
  return step * 4;
});
const ticks = computed(() => [0, 1, 2, 3, 4].map((i) => ({ value: (yMax.value / 4) * i, y: TOP + plotH - (plotH / 4) * i })));
const bars = computed(() => {
  const band = plotW / Math.max(props.days.length, 1);
  const width = Math.min(30, band * 0.46);
  const scale = (n: number) => (n / yMax.value) * plotH;
  return props.days.map((d, i) => {
    const x = LEFT + band * i + (band - width) / 2;
    const realH = scale(d.real), fakeH = scale(d.fake);
    const base = TOP + plotH;
    return { key: d.key, label: d.label, realCount: d.real, fakeCount: d.fake, x, width, cx: x + width / 2, real: { y: base - realH, h: realH }, fake: { y: base - realH - fakeH, h: fakeH }, total: d.fake + d.real, topY: base - realH - fakeH };
  });
});
</script>

<template>
  <svg class="trend" :viewBox="`0 0 ${W} ${H}`" role="img" aria-label="按天统计的检测数量">
    <g v-for="t in ticks" :key="t.value">
      <line class="grid" :class="{ base: t.value === 0 }" :x1="LEFT" :x2="W - RIGHT" :y1="t.y" :y2="t.y" />
      <text class="axis" :x="LEFT - 8" :y="t.y + 4" text-anchor="end">{{ t.value }}</text>
    </g>
    <g v-for="b in bars" :key="b.key">
      <title>{{ b.label }}：真实 {{ b.realCount }} 条，疑似虚假 {{ b.fakeCount }} 条</title>
      <rect v-if="b.real.h > 0" class="real" :x="b.x" :y="b.real.y" :width="b.width" :height="b.real.h" />
      <rect v-if="b.fake.h > 0" class="fake" :x="b.x" :y="b.fake.y" :width="b.width" :height="b.fake.h" />
      <text v-if="b.total" class="total" :x="b.cx" :y="b.topY - 6" text-anchor="middle">{{ b.total }}</text>
      <text class="axis" :x="b.cx" :y="H - 8" text-anchor="middle">{{ b.label }}</text>
    </g>
  </svg>
</template>

<style scoped>
.trend { display: block; width: 100%; height: auto; }
.grid { stroke: var(--color-line); stroke-dasharray: 3 3; }
.grid.base { stroke: var(--color-line-strong); stroke-dasharray: none; }
.axis { fill: var(--color-text-muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.real { fill: var(--color-primary); }
.fake { fill: var(--color-fake); }
.total { fill: var(--color-text-secondary); font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; }
</style>
