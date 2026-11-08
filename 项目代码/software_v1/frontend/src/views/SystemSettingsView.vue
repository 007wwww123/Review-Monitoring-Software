<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { AlertCircle, CheckCircle2, KeyRound, LogOut, UserPlus } from 'lucide-vue-next';
import { ApiError, changePassword, createUser, getCurrentUser, getEvaluations, getEvaluationDetail, logout } from '../api/client';
import { clearSession } from '../auth';
import { accentOptions, applyPreferences, getPreferences, type AccentPreference, type DensityPreference, type ThemePreference } from '../preferences';
import type { CurrentUserResponse, EvaluationResponse } from '../types';
import ModelConfigurationView from './ModelConfigurationView.vue';
import AppCard from '../components/AppCard.vue';
import PageHeader from '../components/layout/PageHeader.vue';
import { NAVIGATION, isGroup } from '../navigation';
import { authenticityLabels, formatDateTime } from '../labels';

const router = useRouter();
const route = useRoute();
type SettingsSection = 'account' | 'appearance' | 'users' | 'models' | 'evaluations';
const settingsSections: SettingsSection[] = ['account', 'appearance', 'users', 'models', 'evaluations'];
const activeSection = computed<SettingsSection>(() => {
  const section = route.hash.slice(1) as SettingsSection;
  return settingsSections.includes(section) ? section : 'account';
});
const user = ref<CurrentUserResponse | null>(null);
const evaluations = ref<EvaluationResponse[]>([]);
const selectedEvaluation = ref<EvaluationResponse | null>(null);
const loading = ref(true);
const accountError = ref(''); const accountSuccess = ref(''); const evaluationError = ref('');
const passwordForm = reactive({ current_password: '', new_password: '', confirm: '' });
const userForm = reactive({ username: '', display_name: '', password: '', role: 'reviewer' as 'reviewer' | 'operator' });
const preferences = reactive(getPreferences());
const savingPassword = ref(false); const creatingUser = ref(false); const signingOut = ref(false);
const metrics = computed(() => selectedEvaluation.value ? [
  ['准确率 Accuracy', selectedEvaluation.value.accuracy], ['精确率 Precision', selectedEvaluation.value.precision], ['召回率 Recall', selectedEvaluation.value.recall], ['F1 值', selectedEvaluation.value.f1], ['AUC', selectedEvaluation.value.auc],
] as const : []);
const matrix = computed(() => {
  const raw = selectedEvaluation.value?.confusion_matrix;
  const labels = raw?.labels; const values = raw?.matrix;
  if (!Array.isArray(labels) || !labels.every((item) => typeof item === 'string') || !Array.isArray(values)) return null;
  if (!values.every((row) => Array.isArray(row) && row.length === labels.length && row.every((value) => typeof value === 'number'))) return null;
  return { labels: labels as string[], values: values as number[][] };
});

// 各分区由侧栏"系统管理"下的菜单进入（/settings#分区），页面标题随分区变化
const sectionMeta: Record<SettingsSection, { title: string; desc: string }> = {
  account: { title: '账户与安全', desc: '查看当前登录账号，修改登录密码' },
  appearance: { title: '界面偏好', desc: '主题、主题色与列表密度，只保存在当前浏览器' },
  users: { title: '账号创建', desc: '创建审核员或操作员账号，不开放公共注册' },
  models: { title: '模型版本', desc: '核对当前进程实际加载的模型登记信息与运行配置' },
  evaluations: { title: '评估历史', desc: '只读展示已保存的历史评估报告' },
};
const meta = computed(() => sectionMeta[activeSection.value]);
// 页头图标与侧栏菜单一致
const sectionIcon = computed(() => NAVIGATION.flatMap((entry) => isGroup(entry) ? entry.children : [entry]).find((leaf) => leaf.key === activeSection.value)?.icon);
// 混淆矩阵按数值深浅着色
const matrixMax = computed(() => Math.max(1, ...(matrix.value?.values.flat() ?? [0])));
const cellStyle = (value: number) => ({ background: `color-mix(in srgb, var(--color-primary) ${Math.round((value / matrixMax.value) * 70) + 6}%, var(--color-surface))`, color: value / matrixMax.value > 0.5 ? 'var(--color-on-primary)' : 'var(--color-text)' });
const matrixLabel = (label: string) => (authenticityLabels as Record<string, string>)[label] ?? label;
const splitLabels: Record<string, string> = { train: '训练集', val: '验证集', test: '测试集', production_review: '线上复核集' };

function metric(value: number | null) { return value === null ? '指标不可用' : `${(value * 100).toFixed(1)}%`; }
function roleLabel(role: string) { return ({ admin: '管理员', reviewer: '审核员', operator: '操作员' } as Record<string, string>)[role] ?? role; }
function savePreferences() { applyPreferences(preferences.theme as ThemePreference, preferences.density as DensityPreference, preferences.accent as AccentPreference); accountSuccess.value = '界面偏好已保存到当前浏览器。'; }

async function loadSettings() {
  loading.value = true; accountError.value = ''; evaluationError.value = '';
  const [userResult, evaluationResult] = await Promise.allSettled([getCurrentUser(), getEvaluations()]);
  if (userResult.status === 'fulfilled') user.value = userResult.value; else accountError.value = userResult.reason instanceof ApiError ? userResult.reason.message : '账户信息加载失败。';
  if (evaluationResult.status === 'fulfilled') { evaluations.value = evaluationResult.value; selectedEvaluation.value = evaluationResult.value[0] ?? null; }
  else evaluationError.value = evaluationResult.reason instanceof ApiError ? evaluationResult.reason.message : '评估历史加载失败。';
  loading.value = false;
}

async function selectEvaluation(item: EvaluationResponse) {
  evaluationError.value = '';
  try { selectedEvaluation.value = await getEvaluationDetail(item.report_id); }
  catch (error) { evaluationError.value = error instanceof ApiError ? error.message : '评估详情加载失败。'; }
}

async function submitPassword() {
  accountError.value = ''; accountSuccess.value = '';
  if (passwordForm.new_password !== passwordForm.confirm) { accountError.value = '两次输入的新密码不一致。'; return; }
  savingPassword.value = true;
  try { await changePassword({ current_password: passwordForm.current_password, new_password: passwordForm.new_password }); clearSession(); await router.replace('/login'); }
  catch (error) { accountError.value = error instanceof ApiError ? error.message : '密码修改失败。'; }
  finally { savingPassword.value = false; }
}

async function submitUser() {
  accountError.value = ''; accountSuccess.value = ''; creatingUser.value = true;
  try { const created = await createUser({ username: userForm.username, display_name: userForm.display_name || undefined, password: userForm.password, role: userForm.role }); accountSuccess.value = `账号 ${created.username} 已创建。`; Object.assign(userForm, { username: '', display_name: '', password: '', role: 'reviewer' }); }
  catch (error) { accountError.value = error instanceof ApiError ? error.message : '账号创建失败。'; }
  finally { creatingUser.value = false; }
}

async function signOut() {
  signingOut.value = true;
  try { await logout(); } catch { clearSession(); }
  await router.replace('/login');
}

onMounted(loadSettings);
</script>

<template>
  <section class="page settings-page">
    <PageHeader :title="meta.title" :desc="meta.desc" :icon="sectionIcon" />

    <div class="settings-main" :class="`section-${activeSection}`">
      <div v-if="accountError && (activeSection === 'account' || activeSection === 'users')" class="alert-bar settings-message is-error" role="alert"><AlertCircle :size="16" />{{ accountError }}</div>
      <div v-if="accountSuccess && (activeSection === 'account' || activeSection === 'appearance' || activeSection === 'users')" class="alert-bar ok settings-message"><CheckCircle2 :size="16" />{{ accountSuccess }}</div>

      <section v-show="activeSection === 'account'" id="account" class="account-grid">
        <AppCard title="账户信息" subtitle="当前登录账号" class="account-card">
          <div v-if="loading" class="empty-hint"><span class="spinner dark"></span>正在加载账户信息…</div>
          <template v-else-if="user">
            <div class="profile">
              <span class="profile-avatar">{{ user.username.slice(0, 1).toUpperCase() }}</span>
              <div><strong>{{ user.display_name || user.username }}</strong><span class="tag primary">{{ roleLabel(user.role) }}</span></div>
            </div>
            <dl class="profile-facts">
              <div><dt>用户名</dt><dd>{{ user.username }}</dd></div>
              <div><dt>显示名称</dt><dd>{{ user.display_name || '未设置' }}</dd></div>
              <div><dt>最后登录</dt><dd class="num">{{ user.last_login_at ? formatDateTime(user.last_login_at) : '暂无记录' }}</dd></div>
            </dl>
            <div class="logout-row">
              <p>退出后本地令牌将被清除，服务端令牌按原过期时间失效。</p>
              <button type="button" class="btn" :disabled="signingOut" @click="signOut"><LogOut :size="15" />退出登录</button>
            </div>
          </template>
        </AppCard>
        <AppCard v-if="user" title="修改密码" subtitle="修改成功后需要重新登录" class="account-card">
          <form class="settings-form password-form" @submit.prevent="submitPassword">
            <label class="ui-field"><span>当前密码</span><input v-model="passwordForm.current_password" class="ui-input" type="password" required autocomplete="current-password" /></label>
            <label class="ui-field"><span>新密码<small>至少 8 位</small></span><input v-model="passwordForm.new_password" class="ui-input" type="password" minlength="8" required autocomplete="new-password" /></label>
            <label class="ui-field"><span>确认新密码</span><input v-model="passwordForm.confirm" class="ui-input" type="password" minlength="8" required autocomplete="new-password" /></label>
            <button class="btn primary" :disabled="savingPassword"><KeyRound :size="15" />{{ savingPassword ? '提交中…' : '修改密码' }}</button>
          </form>
        </AppCard>
      </section>

      <AppCard v-show="activeSection === 'appearance'" id="appearance" title="显示设置" subtitle="只保存在当前浏览器">
        <div class="form-row two">
          <label class="ui-field"><span>主题</span><select v-model="preferences.theme" class="ui-input"><option value="system">跟随系统</option><option value="light">浅色</option><option value="dark">深色</option></select></label>
          <label class="ui-field"><span>列表密度</span><select v-model="preferences.density" class="ui-input"><option value="standard">标准</option><option value="compact">紧凑</option></select></label>
        </div>
        <div class="ui-field accent-field">
          <span>主题色</span>
          <div class="accent-options" role="radiogroup" aria-label="主题色">
            <label v-for="option in accentOptions" :key="option.value" :class="{ on: preferences.accent === option.value }">
              <input v-model="preferences.accent" type="radio" name="accent" :value="option.value" class="sr-only" />
              <i :style="{ background: option.color }"></i>{{ option.label }}
            </label>
          </div>
        </div>
        <button type="button" class="btn primary" @click="savePreferences">保存界面偏好</button>
      </AppCard>

      <AppCard v-if="user?.role === 'admin'" v-show="activeSection === 'users'" id="users" title="创建系统账号" subtitle="只能创建审核员或操作员，不开放公共注册">
        <form class="settings-form user-create-form" @submit.prevent="submitUser">
          <div class="form-row two">
            <label class="ui-field"><span>用户名<small>字母、数字、_ . -</small></span><input v-model="userForm.username" class="ui-input" minlength="3" maxlength="64" pattern="[A-Za-z0-9_.-]+" required /></label>
            <label class="ui-field"><span>显示名称<small>选填</small></span><input v-model="userForm.display_name" class="ui-input" maxlength="100" /></label>
            <label class="ui-field"><span>初始密码<small>至少 8 位</small></span><input v-model="userForm.password" class="ui-input" type="password" minlength="8" required /></label>
            <label class="ui-field"><span>角色</span><select v-model="userForm.role" class="ui-input"><option value="reviewer">审核员</option><option value="operator">操作员</option></select></label>
          </div>
          <button class="btn primary" :disabled="creatingUser"><UserPlus :size="15" />{{ creatingUser ? '创建中…' : '创建账号' }}</button>
        </form>
      </AppCard>

      <AppCard v-show="activeSection === 'models'" id="models" title="模型版本与配置" subtitle="核对当前进程实际加载的模型登记信息">
        <ModelConfigurationView embedded />
      </AppCard>

      <AppCard v-show="activeSection === 'evaluations'" id="evaluations" title="模型评估历史" subtitle="只读展示已保存的历史评估报告">
        <template #extra><button class="btn small" disabled title="真实评估流程尚未通过部署验证">发起评估</button></template>
        <div v-if="evaluationError" class="alert-bar" role="alert"><AlertCircle :size="16" />{{ evaluationError }}</div>
        <div v-else-if="!evaluations.length" class="empty-hint">没有可验证的历史评估记录</div>
        <div v-else class="evaluation-layout">
          <div class="evaluation-list">
            <button v-for="item in evaluations" :key="item.report_id" type="button" :class="{ selected: selectedEvaluation?.report_id === item.report_id }" @click="selectEvaluation(item)">
              <strong>{{ item.dataset_name }}</strong>
              <span class="num">{{ splitLabels[item.dataset_split] ?? item.dataset_split }} · {{ item.sample_count }} 条</span>
              <small class="num">{{ formatDateTime(item.created_at) }}</small>
            </button>
          </div>
          <div v-if="selectedEvaluation" class="evaluation-detail">
            <div class="metric-grid">
              <div v-for="([label, value]) in metrics" :key="label" :class="{ empty: value === null }"><span>{{ label }}</span><strong class="num">{{ metric(value) }}</strong></div>
            </div>
            <h4>混淆矩阵</h4>
            <div v-if="matrix" class="matrix-wrap">
              <table>
                <thead><tr><th>实际 \ 预测</th><th v-for="label in matrix.labels" :key="label">{{ matrixLabel(label) }}</th></tr></thead>
                <tbody><tr v-for="(row, rowIndex) in matrix.values" :key="rowIndex"><th>{{ matrixLabel(matrix.labels[rowIndex]) }}</th><td v-for="(value, columnIndex) in row" :key="columnIndex" class="num" :style="cellStyle(value)">{{ value }}</td></tr></tbody>
              </table>
            </div>
            <p v-else class="hint">当前混淆矩阵结构无法展示。</p>
          </div>
        </div>
        <p class="evaluation-boundary"><AlertCircle :size="14" />测试集不得参与训练、模型选择、阈值选择或调参。真实评估流程可验证前，禁止从页面发起评估。</p>
      </AppCard>
    </div>
  </section>
</template>

<style scoped>
.settings-main { min-width: 0; }

/* 账户分区：两张卡片等高，左卡底部放退出登录 */
.account-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: stretch; gap: 16px; }
.account-card { display: flex; flex-direction: column; }
.profile { display: flex; align-items: center; gap: 14px; }
.profile-avatar { display: grid; flex: none; width: 56px; height: 56px; place-items: center; border-radius: 50%; background: var(--color-primary); color: var(--color-on-primary); font-size: 22px; font-weight: 600; }
.profile strong { display: block; margin-bottom: 4px; font-size: 18px; font-weight: 600; }
.profile-facts { margin: 16px 0 0; font-size: 13px; }
.profile-facts div { display: flex; justify-content: space-between; padding: 11px 0; border-bottom: 1px solid var(--color-line); }
.profile-facts dt { color: var(--color-text-muted); }
.profile-facts dd { margin: 0; font-weight: 500; }
.logout-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: auto; padding-top: 16px; }
.logout-row p { margin: 0; color: var(--color-text-muted); font-size: 12px; }
.settings-form { display: flex; flex-direction: column; align-items: flex-start; gap: 14px; }
.password-form { flex: 1; align-items: stretch; }
.password-form .btn { align-self: flex-start; margin-top: auto; }
.form-row { display: grid; width: 100%; gap: 14px 16px; }
.form-row.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
#appearance .form-row { max-width: 640px; margin-bottom: 18px; }
.accent-field { margin-bottom: 20px; }
.accent-options { display: flex; flex-wrap: wrap; gap: 10px; }
.accent-options label { display: inline-flex; cursor: pointer; align-items: center; gap: 8px; height: 36px; padding: 0 14px; border: 1px solid var(--color-line-strong); border-radius: var(--radius-control); background: var(--color-surface); color: var(--color-text); font: inherit; font-size: 13px; }
.accent-options label.on { border-color: var(--color-primary); box-shadow: 0 0 0 2px var(--color-primary-soft-2); color: var(--color-primary); }
.accent-options i { width: 16px; height: 16px; border-radius: 4px; }

.evaluation-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 18px; }
.evaluation-list { display: flex; flex-direction: column; gap: 8px; }
.evaluation-list button { display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; border: 1px solid var(--color-line); border-radius: var(--radius-card); background: var(--color-surface); color: var(--color-text); font: inherit; text-align: left; cursor: pointer; }
.evaluation-list button:hover { border-color: var(--color-primary); }
.evaluation-list button.selected { border-color: var(--color-primary); background: var(--color-primary-soft); }
.evaluation-list strong { font-size: 13px; }
.evaluation-list span, .evaluation-list small { color: var(--color-text-muted); font-size: 12px; }
.metric-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-bottom: 18px; }
.metric-grid div { padding: 14px; border: 1px solid var(--color-line); border-radius: var(--radius-card); background: var(--color-surface); }
.metric-grid div.empty { background: var(--color-surface-muted); }
.metric-grid span { display: block; color: var(--color-text-muted); font-size: 12px; }
.metric-grid strong { display: block; margin-top: 4px; color: var(--color-text); font-size: 22px; font-weight: 600; }
.metric-grid .empty strong { color: var(--color-text-muted); font-size: 14px; }
h4 { margin: 0 0 10px; font-size: 14px; }
.matrix-wrap { overflow-x: auto; }
.matrix-wrap table { border-collapse: separate; border-spacing: 4px; font-size: 13px; }
.matrix-wrap th { padding: 6px 10px; color: var(--color-text-muted); font-size: 12px; font-weight: 600; text-align: center; white-space: nowrap; }
.matrix-wrap tbody th { text-align: right; }
.matrix-wrap td { min-width: 80px; padding: 14px; border-radius: var(--radius-control); font-weight: 600; text-align: center; }
.evaluation-boundary { display: flex; align-items: center; gap: 6px; margin: 16px 0 0; padding-top: 12px; border-top: 1px solid var(--color-line); color: var(--color-warn); font-size: 12px; }

@media (max-width: 1120px) {
  .evaluation-layout { grid-template-columns: 1fr; }
  .metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 860px) {
  .form-row.two, .account-grid { grid-template-columns: 1fr; }
}
</style>
