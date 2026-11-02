import { createApp } from 'vue';
import App from './App.vue';
import { router } from './router';
import './styles.css';
import './styles/tokens.css';
import { applyPreferences, getPreferences } from './preferences';

function bootstrap() {
  const preferences = getPreferences(); applyPreferences(preferences.theme, preferences.density);
  createApp(App).use(router).mount('#app');
}
bootstrap();
