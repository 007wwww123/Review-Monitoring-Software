// 手写 SVG 图表共用的几何计算
export function polar(cx: number, cy: number, r: number, angle: number): [number, number] {
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

// 从 startAngle 顺时针画到 endAngle 的圆弧路径（弧度）
export function arcPath(cx: number, cy: number, r: number, startAngle: number, endAngle: number): string {
  const [x0, y0] = polar(cx, cy, r, startAngle);
  const [x1, y1] = polar(cx, cy, r, endAngle);
  const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
  return `M ${x0} ${y0} A ${r} ${r} 0 ${largeArc} 1 ${x1} ${y1}`;
}
