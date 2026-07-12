/**
 * Theme context — provides the active palette (light/dark) to every component.
 * Persisted to AsyncStorage. Default: 'light'.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { darkPalette, lightPalette, makeShadow, type Palette } from '@/theme/theme';

export type ThemeMode = 'light' | 'dark';

const THEME_KEY = 'docchat.theme';

interface ThemeValue {
  mode: ThemeMode;
  palette: Palette;
  shadow: ReturnType<typeof makeShadow>;
  setMode: (mode: ThemeMode) => Promise<void>;
  toggle: () => Promise<void>;
  isDark: boolean;
}

const ThemeContext = createContext<ThemeValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>('light');

  useEffect(() => {
    AsyncStorage.getItem(THEME_KEY).then((saved) => {
      if (saved === 'dark' || saved === 'light') setModeState(saved);
    });
  }, []);

  const setMode = useCallback(async (m: ThemeMode) => {
    setModeState(m);
    await AsyncStorage.setItem(THEME_KEY, m);
  }, []);

  const toggle = useCallback(async () => {
    const next: ThemeMode = mode === 'light' ? 'dark' : 'light';
    await setMode(next);
  }, [mode, setMode]);

  const palette = mode === 'dark' ? darkPalette : lightPalette;
  const shadow = makeShadow(palette.accent);

  const value = useMemo(
    () => ({ mode, palette, shadow, setMode, toggle, isDark: mode === 'dark' }),
    [mode, palette, shadow, setMode, toggle],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
