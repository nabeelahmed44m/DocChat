/**
 * App settings — currently just the backend base URL, persisted with
 * AsyncStorage and exposed through context so any screen can read/update it.
 *
 * The base URL is a user setting (not a build constant) because during
 * development the phone talks to a laptop on the LAN, and in production it
 * points at the deployed API. A sensible platform default is provided.
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
import { Platform } from 'react-native';

const BASE_URL_KEY = 'docchat.baseUrl';
const API_KEY_KEY = 'docchat.apiKey';

// Default points at the active Cloudflare tunnel so fresh installs work on device.
// Update this whenever the tunnel URL changes.
export const DEFAULT_BASE_URL = 'https://differential-reports-merchant-memorabilia.trycloudflare.com';

interface SettingsValue {
  baseUrl: string;
  setBaseUrl: (url: string) => Promise<void>;
  apiKey: string;
  setApiKey: (key: string) => Promise<void>;
  ready: boolean;
}

const SettingsContext = createContext<SettingsValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [baseUrl, setBaseUrlState] = useState(DEFAULT_BASE_URL);
  const [apiKey, setApiKeyState] = useState('');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    Promise.all([
      AsyncStorage.getItem(BASE_URL_KEY),
      AsyncStorage.getItem(API_KEY_KEY),
    ])
      .then(([storedUrl, storedKey]) => {
        if (storedUrl) setBaseUrlState(storedUrl);
        if (storedKey) setApiKeyState(storedKey);
      })
      .finally(() => setReady(true));
  }, []);

  const setBaseUrl = useCallback(async (url: string) => {
    const trimmed = url.trim().replace(/\/+$/, '');
    setBaseUrlState(trimmed);
    await AsyncStorage.setItem(BASE_URL_KEY, trimmed);
  }, []);

  const setApiKey = useCallback(async (key: string) => {
    const trimmed = key.trim();
    setApiKeyState(trimmed);
    await AsyncStorage.setItem(API_KEY_KEY, trimmed);
  }, []);

  const value = useMemo(
    () => ({ baseUrl, setBaseUrl, apiKey, setApiKey, ready }),
    [baseUrl, setBaseUrl, apiKey, setApiKey, ready],
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
