/**
 * App settings — the backend base URL is a build-time constant taken from
 * mobile/.env (EXPO_PUBLIC_API_URL); the optional API key is a user setting
 * persisted with AsyncStorage. Both are exposed through context so any
 * screen can read them.
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

const API_KEY_KEY = 'gist.apiKey';

// Backend URL comes from the build environment (mobile/.env). Expo inlines
// EXPO_PUBLIC_* vars at build time; restart the dev server after changing it.
export const DEFAULT_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL?.trim().replace(/\/+$/, '') ||
  'http://127.0.0.1:8000';

interface SettingsValue {
  baseUrl: string;
  apiKey: string;
  setApiKey: (key: string) => Promise<void>;
  ready: boolean;
}

const SettingsContext = createContext<SettingsValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKeyState] = useState('');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(API_KEY_KEY)
      .then((storedKey) => {
        if (storedKey) setApiKeyState(storedKey);
      })
      .finally(() => setReady(true));
  }, []);

  const setApiKey = useCallback(async (key: string) => {
    const trimmed = key.trim();
    setApiKeyState(trimmed);
    await AsyncStorage.setItem(API_KEY_KEY, trimmed);
  }, []);

  const value = useMemo(
    () => ({ baseUrl: DEFAULT_BASE_URL, apiKey, setApiKey, ready }),
    [apiKey, setApiKey, ready],
  );

  return (
    <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
  );
}

export function useSettings(): SettingsValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within a SettingsProvider');
  return ctx;
}
