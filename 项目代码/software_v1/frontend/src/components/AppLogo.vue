<template>
  <span class="app-logo" aria-hidden="true">
    <svg viewBox="0 0 32 32">
      <!-- 两路数据（语义、行为）汇入一点：对应双流门控融合 -->
      <path d="M7 10.5c5 0 7.5 5.5 12.5 5.5" />
      <path class="behavior" d="M7 21.5c5 0 7.5-5.5 12.5-5.5" />
      <circle cx="23.5" cy="16" r="3.5" />
    </svg>
  </span>
</template>

<style scoped>
.app-logo { display: grid; flex: none; width: 32px; height: 32px; place-items: center; border-radius: 8px; background: linear-gradient(135deg, var(--color-primary-hover), var(--color-primary-active)); }
svg { width: 26px; height: 26px; }
path { fill: none; stroke: #fff; stroke-width: 2.6; stroke-linecap: round; }
path.behavior { stroke: rgb(255 255 255 / 62%); }
circle { fill: #fff; }
</style>
