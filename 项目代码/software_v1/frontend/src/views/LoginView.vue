<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
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
  <section class="page-content login-page" aria-labelledby="login-title"><form class="form-panel login-panel" @submit.prevent="submit">
    <h1 id="login-title">系统登录</h1><p>请输入审核账号继续。</p><small class="login-register-note">账号由系统管理员创建，不开放公共注册。</small>
    <label class="field"><span>用户名</span><input v-model="username" autocomplete="username" required /></label>
    <label class="field"><span>密码</span><input v-model="password" type="password" autocomplete="current-password" required /></label>
    <p v-if="error" class="alert error" role="alert">{{ error }}</p>
    <button type="submit" class="primary-button" :disabled="loading">{{ loading ? '登录中' : '登录' }}</button>
  </form></section>
</template>
