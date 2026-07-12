/**
 * Auth context — JWT token + user profile, persisted to AsyncStorage.
 * Exposes login, register, logout, and updateProfile actions.
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

import { useSettings } from './settings';

const TOKEN_KEY = 'docchat.token';
const USER_KEY = 'docchat.user';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  created_at: string;
  updated_at: string;
}

interface AuthValue {
  user: AuthUser | null;
  token: string | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  updateProfile: (name: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { baseUrl } = useSettings();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    Promise.all([AsyncStorage.getItem(TOKEN_KEY), AsyncStorage.getItem(USER_KEY)])
      .then(([t, u]) => {
        if (t) setToken(t);
        if (u) setUser(JSON.parse(u));
      })
      .finally(() => setReady(true));
  }, []);

  const _save = useCallback(async (t: string, u: AuthUser) => {
    setToken(t);
    setUser(u);
    await AsyncStorage.setItem(TOKEN_KEY, t);
    await AsyncStorage.setItem(USER_KEY, JSON.stringify(u));
  }, []);

  const _post = useCallback(
    async (path: string, body: object, authToken?: string) => {
      const res = await fetch(`${baseUrl}${path}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? 'Request failed');
      return data;
    },
    [baseUrl],
  );

  const _put = useCallback(
    async (path: string, body: object, authToken: string) => {
      const res = await fetch(`${baseUrl}${path}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? 'Request failed');
      return data;
    },
    [baseUrl],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await _post('/auth/login', { email, password });
      await _save(data.token, data.user);
    },
    [_post, _save],
  );

  const register = useCallback(
    async (email: string, name: string, password: string) => {
      const data = await _post('/auth/register', { email, name, password });
      await _save(data.token, data.user);
    },
    [_post, _save],
  );

  const updateProfile = useCallback(
    async (name: string) => {
      if (!token) throw new Error('Not logged in');
      const updated = await _put('/auth/profile', { name }, token);
      const newUser = { ...user!, ...updated };
      setUser(newUser);
      await AsyncStorage.setItem(USER_KEY, JSON.stringify(newUser));
    },
    [_put, token, user],
  );

  const logout = useCallback(async () => {
    setToken(null);
    setUser(null);
    await AsyncStorage.multiRemove([TOKEN_KEY, USER_KEY]);
  }, []);

  const value = useMemo(
    () => ({ user, token, ready, login, register, updateProfile, logout }),
    [user, token, ready, login, register, updateProfile, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
