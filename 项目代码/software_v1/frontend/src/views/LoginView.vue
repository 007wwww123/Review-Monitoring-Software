<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { AlertCircle, LockKeyhole, UserRound } from 'lucide-vue-next';
import { ApiError, login } from '../api/client';

const username = ref(''); const password = ref(''); const error = ref(''); const loading = ref(false);
const router = useRouter(); const route = useRoute();
async function submit() {
  if (loading.value) return;
  error.value = ''; loading.value = true;
  try {
    await login({ username: username.value, password: password.value });
    const redirect = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/')
      ? route.query.redirect
      : '/overview';
    await router.replace(redirect);
  }
  catch (e) { error.value = e instanceof ApiError ? e.message : '登录失败'; }
  finally { loading.value = false; }
}
</script>

<template>
  <section class="login-card" aria-labelledby="login-title">
    <form @submit.prevent="submit">
      <h2 id="login-title">账号登录</h2>
      <p class="login-sub">请输入审核账号继续使用系统</p>
      <label class="ui-field">
        <span>用户名</span>
        <span class="input-icon"><UserRound :size="16" /><input v-model="username" class="ui-input" autocomplete="username" placeholder="请输入用户名" required /></span>
      </label>
      <label class="ui-field">
        <span>密码</span>
        <span class="input-icon"><LockKeyhole :size="16" /><input v-model="password" class="ui-input" type="password" autocomplete="current-password" placeholder="请输入密码" required /></span>
      </label>
      <p v-if="error" class="alert-bar" role="alert"><AlertCircle :size="16" />{{ error }}</p>
      <button type="submit" class="btn primary login-submit" :disabled="loading">{{ loading ? '登录中' : '登录' }}</button>
      <small class="login-note">账号由系统管理员创建，不开放公共注册。</small>
    </form>
  </section>
</template>

<style scoped>
.login-card { width: min(100%, 400px); padding: 36px 34px; border-radius: 16px; background: var(--color-surface); box-shadow: 0 10px 40px rgb(22 26 51 / 8%), var(--shadow-card); }
form { display: flex; flex-direction: column; gap: 16px; }
h2 { margin: 0; font-size: 24px; }
.login-sub { margin: -10px 0 6px; color: var(--color-text-muted); font-size: 14px; }
.input-icon { position: relative; display: block; }
.input-icon svg { position: absolute; top: 50%; left: 12px; color: var(--color-text-muted); transform: translateY(-50%); }
.input-icon .ui-input { padding: 10px 12px 10px 38px; }
.alert-bar { margin: 0; }
.login-submit { width: 100%; padding: 10px 14px; margin-top: 4px; font-size: 15px; }
.login-note { color: var(--color-text-muted); font-size: 12px; text-align: center; }
</style>
