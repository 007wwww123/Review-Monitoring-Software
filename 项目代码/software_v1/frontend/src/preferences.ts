export type ThemePreference = 'light' | 'dark' | 'system';
export type DensityPreference = 'standard' | 'compact';
const THEME_KEY = 'review-monitoring.theme';
const DENSITY_KEY = 'review-monitoring.density';

export function getPreferences() {
  const theme = localStorage.getItem(THEME_KEY);
  const density = localStorage.getItem(DENSITY_KEY);
  return {
    theme: (theme === 'light' || theme === 'dark' || theme === 'system' ? theme : 'system') as ThemePreference,
    density: (density === 'compact' ? density : 'standard') as DensityPreference,
  };
}

export function applyPreferences(theme: ThemePreference, density: DensityPreference) {
  localStorage.setItem(THEME_KEY, theme); localStorage.setItem(DENSITY_KEY, density);
  const resolved = theme === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : theme === 'dark' ? 'dark' : 'light';
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.density = density;
}
