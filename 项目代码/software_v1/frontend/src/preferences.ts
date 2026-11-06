export type ThemePreference = 'light' | 'dark' | 'system';
export type DensityPreference = 'standard' | 'compact';
export type AccentPreference = 'blue' | 'ocean' | 'violet';
const THEME_KEY = 'review-monitoring.theme';
const DENSITY_KEY = 'review-monitoring.density';
const ACCENT_KEY = 'review-monitoring.accent';

export const accentOptions: { value: AccentPreference; label: string; color: string }[] = [
  { value: 'blue', label: '科技蓝', color: '#165dff' },
  { value: 'ocean', label: '深海蓝', color: '#0052d9' },
  { value: 'violet', label: '极光紫', color: '#722ed1' },
];

export function getPreferences() {
  const theme = localStorage.getItem(THEME_KEY);
  const density = localStorage.getItem(DENSITY_KEY);
  const accent = localStorage.getItem(ACCENT_KEY);
  return {
    theme: (theme === 'light' || theme === 'dark' || theme === 'system' ? theme : 'system') as ThemePreference,
    density: (density === 'compact' ? density : 'standard') as DensityPreference,
    accent: (accent === 'ocean' || accent === 'violet' ? accent : 'blue') as AccentPreference,
  };
}

export function applyPreferences(theme: ThemePreference, density: DensityPreference, accent: AccentPreference = getPreferences().accent) {
  localStorage.setItem(THEME_KEY, theme); localStorage.setItem(DENSITY_KEY, density); localStorage.setItem(ACCENT_KEY, accent);
  const resolved = theme === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : theme === 'dark' ? 'dark' : 'light';
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.density = density;
  document.documentElement.dataset.accent = accent;
}
