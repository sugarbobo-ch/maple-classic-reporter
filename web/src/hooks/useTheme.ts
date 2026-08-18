import { useState, useEffect, useCallback } from 'react';

export type Theme = 'light' | 'dark';

export function useTheme(
  configTheme?: string,
  onThemePersist?: (theme: Theme) => void
) {
  const [theme, setThemeState] = useState<Theme>(() => {
    if (configTheme === 'dark' || configTheme === 'light') {
      return configTheme as Theme;
    }
    try {
      const saved = localStorage.getItem('maple_theme') as Theme | null;
      if (saved === 'dark' || saved === 'light') return saved;
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        return 'dark';
      }
    } catch {
      // Fallback
    }
    return 'light';
  });

  const applyTheme = useCallback((newTheme: Theme) => {
    document.documentElement.setAttribute('data-theme', newTheme);
    try {
      localStorage.setItem('maple_theme', newTheme);
    } catch {
      // Ignore storage errors
    }
  }, []);

  // Sync with backend config if it loads or changes
  useEffect(() => {
    if (configTheme && (configTheme === 'dark' || configTheme === 'light') && configTheme !== theme) {
      setThemeState(configTheme as Theme);
      applyTheme(configTheme as Theme);
    }
  }, [configTheme, theme, applyTheme]);

  const setTheme = useCallback(
    (newTheme: Theme) => {
      setThemeState(newTheme);
      applyTheme(newTheme);
      if (onThemePersist) {
        onThemePersist(newTheme);
      }
    },
    [applyTheme, onThemePersist]
  );

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next: Theme = prev === 'light' ? 'dark' : 'light';
      applyTheme(next);
      if (onThemePersist) {
        onThemePersist(next);
      }
      return next;
    });
  }, [applyTheme, onThemePersist]);

  useEffect(() => {
    applyTheme(theme);
  }, [theme, applyTheme]);

  return {
    theme,
    isDark: theme === 'dark',
    setTheme,
    toggleTheme,
  };
}

export default useTheme;
