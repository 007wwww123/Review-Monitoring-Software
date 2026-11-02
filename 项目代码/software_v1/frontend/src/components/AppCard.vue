<script setup lang="ts">
// 页面卡片：标题前有主色竖条，副标题可选，右上角放标签或操作（extra 插槽）
defineProps<{ title?: string; subtitle?: string }>();
</script>

<template>
  <section class="app-card">
    <header v-if="title" class="card-head">
      <h2>{{ title }}</h2>
      <div v-if="$slots.extra" class="card-extra"><slot name="extra" /></div>
    </header>
    <p v-if="subtitle" class="card-sub">{{ subtitle }}</p>
    <slot />
  </section>
</template>

<style scoped>
.app-card { padding: 18px 20px; border-radius: var(--radius-card); background: var(--color-surface); box-shadow: var(--shadow-card); }
.card-head { display: flex; align-items: center; gap: 8px; }
.card-head h2 { display: flex; align-items: center; gap: 8px; margin: 0; font-size: 15px; }
.card-head h2::before { width: 4px; height: 15px; border-radius: 2px; background: var(--color-primary); content: ""; }
.card-extra { display: flex; gap: 8px; margin-left: auto; }
.card-sub { margin: 2px 0 14px 12px; color: var(--color-text-muted); font-size: 12px; }
.card-head + :not(.card-sub) { margin-top: 14px; }
</style>
