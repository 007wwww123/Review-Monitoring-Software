// 侧栏菜单、顶栏面包屑和标签页共用的导航结构
import type { Component } from 'vue';
import {
  ChartColumn, ClipboardCheck, Cpu, FileSearch, History, Layers3, LayoutDashboard, Palette, ScanSearch,
  Settings, ShieldCheck, UserPlus, UserRound,
} from 'lucide-vue-next';

export interface NavLeaf { key: string; label: string; icon: Component; to: string; badge?: 'review'; adminOnly?: boolean }
export interface NavGroup { key: string; label: string; icon: Component; children: NavLeaf[] }
export type NavEntry = NavLeaf | NavGroup;

export const isGroup = (entry: NavEntry): entry is NavGroup => 'children' in entry;

export const NAVIGATION: NavEntry[] = [
  { key: 'overview', label: '系统概览', icon: LayoutDashboard, to: '/overview' },
  { key: 'audit', label: '审核工作台', icon: ShieldCheck, children: [
    { key: 'review', label: '待复核队列', icon: ClipboardCheck, to: '/review', badge: 'review' },
    { key: 'results', label: '检测记录', icon: History, to: '/results' },
  ] },
  { key: 'detect', label: '发起检测', icon: ScanSearch, children: [
    { key: 'single', label: '单条评论检测', icon: FileSearch, to: '/detections/single' },
    { key: 'batch', label: '批量检测任务', icon: Layers3, to: '/detections/batch' },
  ] },
  { key: 'system', label: '系统管理', icon: Settings, children: [
    { key: 'account', label: '账户与安全', icon: UserRound, to: '/settings#account' },
    { key: 'appearance', label: '界面偏好', icon: Palette, to: '/settings#appearance' },
    { key: 'users', label: '账号创建', icon: UserPlus, to: '/settings#users', adminOnly: true },
    { key: 'models', label: '模型版本', icon: Cpu, to: '/settings#models' },
    { key: 'evaluations', label: '评估历史', icon: ChartColumn, to: '/settings#evaluations' },
  ] },
];

export interface NavMatch { group?: NavGroup; leaf: NavLeaf; detail?: string }

// 按当前路由找到对应的菜单项。结果详情页归属"检测记录"；设置页按 hash 区分分区，无 hash 时为账户与安全
export function matchRoute(path: string, hash: string, params: Record<string, unknown> = {}): NavMatch | null {
  for (const entry of NAVIGATION) {
    const leaves = isGroup(entry) ? entry.children : [entry];
    for (const leaf of leaves) {
      const [leafPath, leafHash] = leaf.to.split('#');
      const group = isGroup(entry) ? entry : undefined;
      if (leafHash !== undefined) {
        if (path === leafPath && (hash.slice(1) || 'account') === leafHash) return { group, leaf };
      } else if (path === leafPath) {
        return { group, leaf };
      } else if (path.startsWith(`${leafPath}/`)) {
        return { group, leaf, detail: params.resultId ? `结果详情 #${params.resultId}` : '详情' };
      }
    }
  }
  return null;
}
