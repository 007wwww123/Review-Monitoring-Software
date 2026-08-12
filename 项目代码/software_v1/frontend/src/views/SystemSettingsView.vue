<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { AlertCircle, CheckCircle2, KeyRound, LogOut, Plus, UserRound } from 'lucide-vue-next';
import { ApiError, changePassword, createUser, getCurrentUser, getEvaluations, getEvaluationDetail, logout } from '../api/client';
import { clearSession } from '../auth';
import { applyPreferences, getPreferences, type DensityPreference, type ThemePreference } from '../preferences';
import type { CurrentUserResponse, EvaluationResponse } from '../types';
import ModelConfigurationView from './ModelConfigurationView.vue';

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
const isMock = import.meta.env.VITE_USE_MOCK_API !== 'false';
const metrics = computed(() => selectedEvaluation.value ? [
  ['Accuracy', selectedEvaluation.value.accuracy], ['Precision', selectedEvaluation.value.precision], ['Recall', selectedEvaluation.value.recall], ['F1', selectedEvaluation.value.f1], ['AUC', selectedEvaluation.value.auc],
] as const : []);
const matrix = computed(() => {
  const raw = selectedEvaluation.value?.confusion_matrix;
  const labels = raw?.labels; const values = raw?.matrix;
  if (!Array.isArray(labels) || !labels.every((item) => typeof item === 'string') || !Array.isArray(values)) return null;
  if (!values.every((row) => Array.isArray(row) && row.length === labels.length && row.every((value) => typeof value === 'number'))) return null;
  return { labels: labels as string[], values: values as number[][] };
});

function metric(value: number | null) { return value === null ? '指标不可用' : `${(value * 100).toFixed(1)}%`; }
function roleLabel(role: string) { return ({ admin: '管理员', reviewer: '审核员', operator: '操作员' } as Record<string, string>)[role] ?? role; }
function savePreferences() { applyPreferences(preferences.theme as ThemePreference, preferences.density as DensityPreference); accountSuccess.value = '界面偏好已保存到当前浏览器。'; }

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
  <section class="page-content settings-page">
    <header class="page-heading settings-heading"><div><span class="eyebrow">系统管理</span><h1>系统设置</h1><p>管理账户安全、界面偏好、模型登记与历史评估</p></div></header>
    <nav class="settings-anchor-nav" aria-label="设置分区">
      <RouterLink to="/settings#account" :class="{ active: activeSection === 'account' }">账户</RouterLink>
      <RouterLink to="/settings#appearance" :class="{ active: activeSection === 'appearance' }">界面</RouterLink>
      <RouterLink v-if="user?.role === 'admin'" to="/settings#users" :class="{ active: activeSection === 'users' }">账号创建</RouterLink>
      <RouterLink to="/settings#models" :class="{ active: activeSection === 'models' }">模型</RouterLink>
      <RouterLink to="/settings#evaluations" :class="{ active: activeSection === 'evaluations' }">评估</RouterLink>
    </nav>
    <div v-if="accountError && (activeSection === 'account' || activeSection === 'users')" class="alert error settings-message" role="alert"><AlertCircle :size="17" />{{ accountError }}</div>
    <div v-if="accountSuccess && (activeSection === 'account' || activeSection === 'appearance' || activeSection === 'users')" class="alert success settings-message"><CheckCircle2 :size="17" />{{ accountSuccess }}</div>

    <div class="settings-layout">
      <main class="settings-main" :class="`section-${activeSection}`">
        <section v-show="activeSection === 'account'" id="account" class="settings-section">
          <div class="section-heading"><div><h2>账户信息与安全</h2><p>当前登录账号及密码管理</p></div><UserRound :size="19" /></div>
          <div v-if="loading" class="settings-loading"><span class="spinner dark"></span>正在加载账户信息…</div>
          <template v-else-if="user"><dl class="account-summary"><div><dt>用户名</dt><dd>{{ user.username }}</dd></div><div><dt>显示名称</dt><dd>{{ user.display_name || '未设置' }}</dd></div><div><dt>角色</dt><dd>{{ roleLabel(user.role) }}</dd></div><div><dt>最后登录</dt><dd>{{ user.last_login_at ? new Date(user.last_login_at).toLocaleString('zh-CN') : '暂无记录' }}</dd></div></dl>
            <form class="settings-form" @submit.prevent="submitPassword"><h3><KeyRound :size="16" />修改密码</h3><div class="settings-form-grid"><label class="field"><span>当前密码</span><input v-model="passwordForm.current_password" type="password" required autocomplete="current-password" /></label><label class="field"><span>新密码</span><input v-model="passwordForm.new_password" type="password" minlength="8" required autocomplete="new-password" /></label><label class="field"><span>确认新密码</span><input v-model="passwordForm.confirm" type="password" minlength="8" required autocomplete="new-password" /></label></div><button class="primary-button" :disabled="savingPassword">{{ savingPassword ? '提交中…' : '修改密码' }}</button></form>
            <div class="logout-row"><div><strong>退出当前账号</strong><span>本地令牌将被清除，服务端令牌按原过期时间失效。</span></div><button type="button" class="icon-text-button secondary" :disabled="signingOut" @click="signOut"><LogOut :size="16" />退出登录</button></div>
          </template>
        </section>

        <section id="appearance" class="settings-section"><div class="section-heading"><div><h2>界面偏好</h2><p>仅保存在当前浏览器</p></div></div><div class="preference-grid"><label class="field"><span>主题</span><select v-model="preferences.theme"><option value="system">跟随系统</option><option value="light">浅色</option><option value="dark">深色</option></select></label><label class="field"><span>列表密度</span><select v-model="preferences.density"><option value="standard">标准</option><option value="compact">紧凑</option></select></label></div><button type="button" class="primary-button" @click="savePreferences">保存界面偏好</button></section>

        <section v-if="user?.role === 'admin'" id="users" class="settings-section"><div class="section-heading"><div><h2>创建系统账号</h2><p>仅允许创建审核员或操作员，不开放公共注册</p></div><Plus :size="19" /></div><form class="settings-form user-create-form" @submit.prevent="submitUser"><div class="settings-form-grid"><label class="field"><span>用户名</span><input v-model="userForm.username" minlength="3" maxlength="64" pattern="[A-Za-z0-9_.-]+" required /></label><label class="field"><span>显示名称</span><input v-model="userForm.display_name" maxlength="100" /></label><label class="field"><span>初始密码</span><input v-model="userForm.password" type="password" minlength="8" required /></label><label class="field"><span>角色</span><select v-model="userForm.role"><option value="reviewer">审核员</option><option value="operator">操作员</option></select></label></div><button class="primary-button" :disabled="creatingUser">{{ creatingUser ? '创建中…' : '创建账号' }}</button></form></section>

        <section id="models" class="settings-section settings-model-section"><div class="section-heading settings-section-title"><div><h2>模型版本与配置</h2><p>核对登记信息并切换可用版本</p></div></div><ModelConfigurationView embedded /></section>

        <section id="evaluations" class="settings-section"><div class="section-heading"><div><h2>模型评估历史</h2><p>只读展示已保存的历史报告</p></div><button class="primary-button" disabled title="真实评估适配器尚未配置">发起评估</button></div><div v-if="isMock" class="mock-evaluation-banner"><AlertCircle :size="16" />以下为模拟联调数据，不代表真实模型性能。</div><div v-if="evaluationError" class="alert error" role="alert">{{ evaluationError }}</div><div v-else-if="!evaluations.length" class="settings-empty">没有可验证的历史评估记录</div><div v-else class="evaluation-layout"><div class="evaluation-list"><button v-for="item in evaluations" :key="item.report_id" type="button" :class="{ selected: selectedEvaluation?.report_id === item.report_id }" @click="selectEvaluation(item)"><strong>{{ item.dataset_name }}</strong><span>{{ item.dataset_split }} · {{ item.sample_count }} 条</span><small>{{ new Date(item.created_at).toLocaleDateString('zh-CN') }}</small></button></div><div v-if="selectedEvaluation" class="evaluation-detail"><div class="metric-grid"><div v-for="([label, value]) in metrics" :key="label"><span>{{ label }}</span><strong>{{ metric(value) }}</strong></div></div><div class="matrix-section"><h3>混淆矩阵</h3><div v-if="matrix" class="matrix-wrap"><table><thead><tr><th>实际 / 预测</th><th v-for="label in matrix.labels" :key="label">{{ label }}</th></tr></thead><tbody><tr v-for="(row, rowIndex) in matrix.values" :key="rowIndex"><th>{{ matrix.labels[rowIndex] }}</th><td v-for="(value, columnIndex) in row" :key="columnIndex">{{ value }}</td></tr></tbody></table></div><p v-else>当前混淆矩阵结构无法展示。</p></div></div></div><div class="evaluation-boundary">测试集不得参与训练、模型选择、阈值选择或调参。真实评估流程可验证前，禁止从页面发起评估。</div></section>
      </main>
    </div>
  </section>
</template>
