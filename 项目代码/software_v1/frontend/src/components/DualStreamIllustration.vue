<template>
  <!-- 登录页插图：语义流与行为流汇入门控融合，输出审核建议。画在主色渐变底上，颜色用半透明白和浅紫 -->
  <svg class="dual-stream" viewBox="0 0 420 220" role="img" aria-label="语义流与行为流经门控融合输出审核建议">
    <path class="band semantic" d="M0 50 C 120 50, 150 92, 236 98 L 236 126 C 150 118, 120 82, 0 82 Z" />
    <path class="band behavior" d="M0 150 C 120 150, 150 128, 236 126 L 236 140 C 150 142, 120 168, 0 168 Z" />
    <rect class="gate" x="236" y="88" width="64" height="62" rx="12" />
    <path class="band out" d="M300 104 C 330 104, 340 112, 372 112 L 372 126 C 340 126, 330 134, 300 134 Z" />
    <circle class="result" cx="388" cy="119" r="16" />
    <text x="12" y="40">ALBERT 语义流</text>
    <text x="12" y="192">GRU 行为流</text>
    <text x="268" y="76" text-anchor="middle">门控融合</text>
    <text x="388" y="160" text-anchor="middle">审核建议</text>
  </svg>
</template>

<style scoped>
.dual-stream { display: block; width: 100%; max-width: 440px; }
.band.semantic { fill: rgb(255 255 255 / 78%); }
.band.behavior { fill: #c396ed; }
.band.out { fill: rgb(255 255 255 / 92%); }
.gate { fill: rgb(255 255 255 / 14%); stroke: rgb(255 255 255 / 60%); stroke-width: 1.5; }
.result { fill: #fff; }
text { fill: rgb(255 255 255 / 78%); font-size: 12px; }
</style>
