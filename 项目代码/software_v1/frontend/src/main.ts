import { createApp } from 'vue';
import App from './App.vue';
import { router } from './router';
import './styles/base.css';
import './styles/tokens.css';
import './styles/ui.css';
import { APP_NAME, APP_VERSION } from './brand';
import { applyPreferences, getPreferences } from './preferences';

function bootstrap() {
  document.title = `${APP_NAME} ${APP_VERSION}`;
  const preferences = getPreferences(); applyPreferences(preferences.theme, preferences.density, preferences.accent);
  createApp(App).use(router).mount('#app');
}
bootstrap();
