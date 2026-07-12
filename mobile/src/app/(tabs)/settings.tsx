import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import {
  Alert,
  ScrollView,
  StyleSheet,
  Switch,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import {
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Crown,
  LogOut,
  Mail,
  Moon,
  Pencil,
  Server,
  Sun,
  Trash2,
  User,
  Zap,
  XCircle,
} from 'lucide-react-native';

import { useBillingStatus, useCreateCheckout, useCreatePortal, useHealth } from '@/api/hooks';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Text } from '@/components/ui/Text';
import { useAuth } from '@/lib/auth';
import { DEFAULT_BASE_URL, useSettings } from '@/lib/settings';
import { useTheme } from '@/lib/theme';
import { radius, spacing, typography } from '@/theme/theme';

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
}

export default function SettingsScreen() {
  const router = useRouter();
  const { baseUrl, setBaseUrl } = useSettings();
  const { user, updateProfile, deleteAccount, logout } = useAuth();
  const { palette, isDark, toggle } = useTheme();
  const health = useHealth();
  const billing = useBillingStatus();
  const checkout = useCreateCheckout();
  const portal = useCreatePortal();
  const isPro = billing.data?.plan === 'pro';

  const handleUpgrade = async () => {
    try {
      const { url } = await checkout.mutateAsync();
      await WebBrowser.openAuthSessionAsync(url, 'gist://billing');
      billing.refetch();
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Could not open checkout.');
    }
  };

  const handleManageSubscription = async () => {
    try {
      const { url } = await portal.mutateAsync();
      await WebBrowser.openBrowserAsync(url);
      billing.refetch();
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Could not open portal.');
    }
  };

  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [savingName, setSavingName] = useState(false);

  const [editingServer, setEditingServer] = useState(false);
  const [urlDraft, setUrlDraft] = useState(baseUrl);
  const [savedUrl, setSavedUrl] = useState(false);

  const isConnected = !health.isLoading && !health.isError && !!health.data;

  const styles = useMemo(
    () =>
      StyleSheet.create({
        container: { flex: 1, backgroundColor: palette.bg },
        content: { padding: spacing.lg, paddingBottom: 60 },

        section: {
          marginBottom: spacing.xs,
          marginTop: spacing.xl,
          letterSpacing: 0.6,
        },

        // Profile card
        avatarRow: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.lg,
          paddingVertical: spacing.sm,
        },
        avatar: {
          width: 56,
          height: 56,
          borderRadius: 28,
          backgroundColor: palette.accentSoft,
          alignItems: 'center',
          justifyContent: 'center',
        },
        avatarInitial: { fontSize: 22, fontWeight: '700', color: palette.accent },
        profileInfo: { flex: 1 },
        editBtn: {
          width: 32,
          height: 32,
          borderRadius: 16,
          backgroundColor: palette.surfacePressed,
          alignItems: 'center',
          justifyContent: 'center',
        },

        // Info rows inside cards
        infoRow: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.md,
          paddingVertical: spacing.md,
        },
        divider: { height: 1, backgroundColor: palette.border },
        infoLabel: { flex: 1 },

        // Inline edit
        editRow: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.sm,
          paddingVertical: spacing.sm,
        },
        nameInput: {
          flex: 1,
          color: palette.text,
          ...typography.body,
          borderBottomWidth: 1,
          borderBottomColor: palette.accent,
          paddingVertical: spacing.xs,
        },
        editActions: {
          flexDirection: 'row',
          gap: spacing.sm,
          marginTop: spacing.sm,
        },

        // Server row
        urlInput: {
          flex: 1,
          color: palette.text,
          ...typography.body,
        },

        // Row button (server toggle, sign out etc.)
        rowBtn: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.md,
          paddingVertical: spacing.md,
        },
        rowBtnLabel: { flex: 1 },

        // Theme row
        themeRow: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.md,
          paddingVertical: spacing.md,
        },
        themeText: { flex: 1 },

        // Danger zone
        dangerCard: {
          borderWidth: 1,
          borderColor: palette.danger + '40',
          backgroundColor: palette.dangerSoft,
        },

        footer: { marginTop: spacing.xl, textAlign: 'center', lineHeight: 18 },
      }),
    [palette],
  );

  const startEditName = () => {
    setNameDraft(user?.name ?? '');
    setEditingName(true);
  };

  const saveName = async () => {
    if (!nameDraft.trim()) return;
    setSavingName(true);
    try {
      await updateProfile(nameDraft.trim());
      setEditingName(false);
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Could not update profile.');
    } finally {
      setSavingName(false);
    }
  };

  const saveServer = async () => {
    await setBaseUrl(urlDraft || DEFAULT_BASE_URL);
    setSavedUrl(true);
    setTimeout(() => setSavedUrl(false), 1500);
    health.refetch();
    setEditingServer(false);
  };

  const handleLogout = () => {
    Alert.alert('Sign out', 'Are you sure?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign out',
        style: 'destructive',
        onPress: async () => {
          await logout();
          router.replace('/login');
        },
      },
    ]);
  };

  const handleDeleteAccount = () => {
    Alert.alert(
      'Delete account',
      'This permanently deletes your account and all uploaded documents. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete account',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteAccount();
              router.replace('/login');
            } catch (err) {
              Alert.alert('Error', err instanceof Error ? err.message : 'Could not delete account.');
            }
          },
        },
      ],
    );
  };

  const initial = (user?.name ?? user?.email ?? '?')[0].toUpperCase();

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      {/* ── Profile ───────────────────────────────────────────────── */}
      <Text variant="caption" tone="muted" style={styles.section}>PROFILE</Text>
      {user ? (
        <Card>
          {/* Avatar + name */}
          <View style={styles.avatarRow}>
            <View style={styles.avatar}>
              <Text style={styles.avatarInitial}>{initial}</Text>
            </View>
            <View style={styles.profileInfo}>
              <Text variant="bodyStrong">{user.name}</Text>
              <Text variant="caption" tone="faint">Member since {formatDate(user.created_at)}</Text>
            </View>
            <TouchableOpacity style={styles.editBtn} onPress={startEditName} hitSlop={8}>
              <Pencil size={14} color={palette.textMuted} />
            </TouchableOpacity>
          </View>

          {/* Inline name editor */}
          {editingName && (
            <>
              <View style={styles.divider} />
              <View style={styles.editRow}>
                <User size={16} color={palette.accent} />
                <TextInput
                  style={styles.nameInput}
                  value={nameDraft}
                  onChangeText={setNameDraft}
                  placeholder="Your name"
                  placeholderTextColor={palette.textFaint}
                  autoFocus
                  autoCorrect={false}
                  returnKeyType="done"
                  onSubmitEditing={saveName}
                />
              </View>
              <View style={styles.editActions}>
                <Button
                  label={savingName ? 'Saving…' : 'Save'}
                  onPress={saveName}
                  disabled={savingName}
                  style={{ flex: 1 }}
                />
                <Button
                  label="Cancel"
                  onPress={() => setEditingName(false)}
                  variant="ghost"
                  style={{ flex: 1 }}
                />
              </View>
            </>
          )}

          <View style={styles.divider} />

          {/* Email */}
          <View style={styles.infoRow}>
            <Mail size={16} color={palette.textMuted} />
            <View style={styles.infoLabel}>
              <Text variant="caption" tone="faint">Email</Text>
              <Text variant="body">{user.email}</Text>
            </View>
          </View>

          <View style={styles.divider} />

          {/* Joined */}
          <View style={styles.infoRow}>
            <CalendarDays size={16} color={palette.textMuted} />
            <View style={styles.infoLabel}>
              <Text variant="caption" tone="faint">Member since</Text>
              <Text variant="body">{formatDate(user.created_at)}</Text>
            </View>
          </View>
        </Card>
      ) : (
        <Card>
          <View style={styles.rowBtn}>
            <User size={18} color={palette.textMuted} />
            <Text variant="body" tone="muted" style={styles.rowBtnLabel}>Not signed in</Text>
            <Button label="Sign in" onPress={() => router.push('/login')} />
          </View>
        </Card>
      )}

      {/* ── Plan ──────────────────────────────────────────────────── */}
      {user && (
        <>
          <Text variant="caption" tone="muted" style={styles.section}>PLAN</Text>
          <Card>
            <View style={styles.rowBtn}>
              {isPro ? (
                <Crown size={18} color={palette.accent} />
              ) : (
                <Zap size={18} color={palette.textMuted} />
              )}
              <View style={styles.rowBtnLabel}>
                <Text variant="bodyStrong">{isPro ? 'Pro' : 'Free'}</Text>
                <Text variant="caption" tone="faint">
                  {isPro
                    ? `Active${billing.data?.current_period_end ? ' · renews ' + formatDate(billing.data.current_period_end) : ''}`
                    : 'Documents up to 1 MB'}
                </Text>
              </View>
              {isPro ? (
                <Button
                  label={portal.isPending ? '…' : 'Manage'}
                  onPress={handleManageSubscription}
                  variant="ghost"
                />
              ) : (
                <Button
                  label={checkout.isPending ? '…' : 'Upgrade'}
                  onPress={handleUpgrade}
                />
              )}
            </View>
          </Card>
        </>
      )}

      {/* ── Appearance ────────────────────────────────────────────── */}
      <Text variant="caption" tone="muted" style={styles.section}>APPEARANCE</Text>
      <Card>
        <View style={styles.themeRow}>
          {isDark ? (
            <Moon size={18} color={palette.accent} />
          ) : (
            <Sun size={18} color={palette.accent} />
          )}
          <View style={styles.themeText}>
            <Text variant="bodyStrong">{isDark ? 'Dark mode' : 'Light mode'}</Text>
            <Text variant="caption" tone="faint">
              {isDark ? 'Gamma deep dark' : 'Notion warm light'}
            </Text>
          </View>
          <Switch
            value={isDark}
            onValueChange={() => toggle()}
            trackColor={{ true: palette.accent, false: isDark ? palette.surfacePressed : '#C7C7CC' }}
            thumbColor="#FFFFFF"
            ios_backgroundColor={isDark ? palette.surfacePressed : '#C7C7CC'}
            accessibilityLabel="Toggle dark mode"
          />
        </View>
      </Card>

      {/* ── Server ────────────────────────────────────────────────── */}
      <Text variant="caption" tone="muted" style={styles.section}>SERVER</Text>
      <Card>
        {/* Connection status row — always visible */}
        <TouchableOpacity
          style={styles.rowBtn}
          onPress={() => setEditingServer((v) => !v)}
          activeOpacity={0.7}
        >
          <Server size={18} color={isConnected ? palette.success : palette.danger} />
          <View style={styles.rowBtnLabel}>
            {health.isLoading ? (
              <Text variant="body" tone="muted">Checking connection…</Text>
            ) : isConnected ? (
              <>
                <Text variant="bodyStrong" tone="success">Connected</Text>
                <Text variant="caption" tone="faint" numberOfLines={1}>{baseUrl}</Text>
              </>
            ) : (
              <>
                <Text variant="bodyStrong" tone="danger">Not connected</Text>
                <Text variant="caption" tone="faint" numberOfLines={1}>{baseUrl}</Text>
              </>
            )}
          </View>
          {isConnected ? (
            <CheckCircle2 size={18} color={palette.success} />
          ) : (
            <ChevronRight size={16} color={palette.textMuted} />
          )}
        </TouchableOpacity>

        {/* URL editor — only shown when not connected, or when user taps to edit */}
        {(!isConnected || editingServer) && (
          <>
            <View style={styles.divider} />
            <View style={styles.infoRow}>
              <TextInput
                style={[styles.urlInput, { flex: 1 }]}
                value={urlDraft}
                onChangeText={setUrlDraft}
                placeholder={DEFAULT_BASE_URL}
                placeholderTextColor={palette.textFaint}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
              />
            </View>
            <Button
              label={savedUrl ? 'Saved ✓' : 'Save & test connection'}
              onPress={saveServer}
              style={{ marginTop: spacing.xs }}
            />
          </>
        )}

        {/* Supported formats — only when connected */}
        {isConnected && health.data?.supported_extensions && (
          <>
            <View style={styles.divider} />
            <View style={{ paddingTop: spacing.sm, flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs }}>
              {health.data.supported_extensions.map((ext) => (
                <View
                  key={ext}
                  style={{
                    backgroundColor: palette.surfacePressed,
                    paddingHorizontal: spacing.sm,
                    paddingVertical: 3,
                    borderRadius: radius.sm,
                  }}
                >
                  <Text variant="micro" tone="muted">{ext}</Text>
                </View>
              ))}
            </View>
          </>
        )}
      </Card>

      {/* ── Danger zone ───────────────────────────────────────────── */}
      {user && (
        <>
          <Text variant="caption" tone="muted" style={styles.section}>ACCOUNT</Text>
          <Card style={styles.dangerCard}>
            <TouchableOpacity style={styles.rowBtn} onPress={handleLogout} activeOpacity={0.7}>
              <LogOut size={18} color={palette.danger} />
              <Text variant="body" style={[styles.rowBtnLabel, { color: palette.danger }]}>
                Sign out
              </Text>
            </TouchableOpacity>
            <View style={styles.divider} />
            <TouchableOpacity style={styles.rowBtn} onPress={handleDeleteAccount} activeOpacity={0.7}>
              <Trash2 size={18} color={palette.danger} />
              <Text variant="body" style={[styles.rowBtnLabel, { color: palette.danger }]}>
                Delete account
              </Text>
              <Text variant="caption" tone="faint">Permanent</Text>
            </TouchableOpacity>
          </Card>
        </>
      )}

      <Text variant="caption" tone="faint" style={styles.footer}>
        Gist · v1.0.0
      </Text>
    </ScrollView>
  );
}
