import { createApp } from 'vue';
import App from './App.vue';
import { router } from './router';
import './styles.css';

async function bootstrap() {
  if (import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_API !== 'false') {
    const { worker } = await import('./mocks/browser');
    await worker.start({ onUnhandledRequest: 'bypass' });
  }
  createApp(App).use(router).mount('#app');
}

void bootstrap();
