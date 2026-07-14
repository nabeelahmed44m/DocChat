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
  Crown,
  LogOut,
  Mail,
  Moon,
  Pencil,
  Sun,
  Trash2,
  User,
  Zap,
} from 'lucide-react-native';

import { useBillingStatus, useCreateCheckout, useCreatePortal } from '@/api/hooks';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Text } from '@/components/ui/Text';
import { useAuth } from '@/lib/auth';
import { useTheme } from '@/lib/theme';
import { spacing, typography } from '@/theme/theme';

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
  const { user, updateProfile, deleteAccount, logout } = useAuth();
  const { palette, isDark, toggle } = useTheme();
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

        // Row button (sign out etc.)
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
