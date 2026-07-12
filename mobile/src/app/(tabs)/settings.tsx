import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Switch, TextInput, View } from 'react-native';
import { CheckCircle2, LogOut, Moon, Server, Sun, User, XCircle } from 'lucide-react-native';

import { useHealth } from '@/api/hooks';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Text } from '@/components/ui/Text';
import { useAuth } from '@/lib/auth';
import { DEFAULT_BASE_URL, useSettings } from '@/lib/settings';
import { useTheme } from '@/lib/theme';
import { radius, spacing, typography } from '@/theme/theme';

export default function SettingsScreen() {
  const router = useRouter();
  const { baseUrl, setBaseUrl } = useSettings();
  const { user, updateProfile, logout } = useAuth();
  const { palette, isDark, toggle } = useTheme();
  const health = useHealth();
  const [draft, setDraft] = useState(baseUrl);
  const [nameDraft, setNameDraft] = useState(user?.name ?? '');
  const [saved, setSaved] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);

  const styles = useMemo(
    () =>
      StyleSheet.create({
        container: { flex: 1, backgroundColor: palette.bg },
        content: { padding: spacing.lg, paddingBottom: spacing.xxxl },
        flex: { flex: 1 },
        section: { marginBottom: spacing.sm, marginTop: spacing.lg, letterSpacing: 0.6 },
        inputRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.md },
        emailRow: { paddingVertical: spacing.sm, paddingHorizontal: spacing.xs },
        accountRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
        themeRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
        themeText: { flex: 1 },
        divider: { height: 1, backgroundColor: palette.border },
        input: { flex: 1, color: palette.text, ...typography.body },
        hint: { marginTop: spacing.sm, lineHeight: 18 },
        smallBtn: { marginTop: spacing.md },
        signOutBtn: { marginTop: spacing.xl, borderWidth: 1, borderColor: palette.danger, backgroundColor: 'transparent' },
        statusRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
        connected: { gap: spacing.md },
        formats: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
        formatChip: {
          backgroundColor: palette.surfacePressed,
          paddingHorizontal: spacing.sm,
          paddingVertical: 3,
          borderRadius: radius.sm,
        },
        footer: { marginTop: spacing.xl, textAlign: 'center', lineHeight: 18 },
      }),
    [palette],
  );

  const saveServer = async () => {
    await setBaseUrl(draft || DEFAULT_BASE_URL);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
    health.refetch();
  };

  const saveProfile = async () => {
    if (!nameDraft.trim()) return;
    setSavingProfile(true);
    try {
      await updateProfile(nameDraft.trim());
      Alert.alert('Saved', 'Your profile has been updated.');
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Could not update profile.');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleLogout = () => {
    Alert.alert('Sign out', 'Are you sure you want to sign out?', [
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

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      {/* Profile section */}
      {user ? (
        <>
          <Text variant="caption" tone="muted" style={styles.section}>
            PROFILE
          </Text>
          <Card>
            <View style={styles.inputRow}>
              <User size={18} color={palette.textMuted} />
              <TextInput
                style={styles.input}
                value={nameDraft}
                onChangeText={setNameDraft}
                placeholder="Your name"
                placeholderTextColor={palette.textFaint}
                autoCorrect={false}
              />
            </View>
            <View style={styles.divider} />
            <View style={styles.emailRow}>
              <Text variant="caption" tone="faint">
                {user.email}
              </Text>
            </View>
          </Card>
          <Button
            label={savingProfile ? 'Saving…' : 'Save profile'}
            onPress={saveProfile}
            disabled={savingProfile}
            style={styles.smallBtn}
          />
        </>
      ) : (
        <>
          <Text variant="caption" tone="muted" style={styles.section}>
            ACCOUNT
          </Text>
          <Card>
            <View style={styles.accountRow}>
              <Text variant="body" tone="muted">
                Not signed in
              </Text>
              <Button label="Sign in" onPress={() => router.push('/login')} />
            </View>
          </Card>
        </>
      )}

      {/* Appearance */}
      <Text variant="caption" tone="muted" style={styles.section}>
        APPEARANCE
      </Text>
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

      {/* Server address */}
      <Text variant="caption" tone="muted" style={styles.section}>
        SERVER ADDRESS
      </Text>
      <Card>
        <View style={styles.inputRow}>
          <Server size={18} color={palette.textMuted} />
          <TextInput
            style={styles.input}
            value={draft}
            onChangeText={setDraft}
            placeholder={DEFAULT_BASE_URL}
            placeholderTextColor={palette.textFaint}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
          />
        </View>
      </Card>
      <Text variant="caption" tone="faint" style={styles.hint}>
        Use a Cloudflare tunnel URL or your LAN IP for physical device testing.
      </Text>
      <Button
        label={saved ? 'Saved ✓' : 'Save & test connection'}
        onPress={saveServer}
        style={styles.smallBtn}
      />

      {/* Connection status */}
      <Text variant="caption" tone="muted" style={styles.section}>
        CONNECTION
      </Text>
      <Card>
        {health.isLoading ? (
          <Text variant="body" tone="muted">Checking…</Text>
        ) : health.isError ? (
          <View style={styles.statusRow}>
            <XCircle size={20} color={palette.danger} />
            <View style={styles.flex}>
              <Text variant="bodyStrong" tone="danger">Not connected</Text>
              <Text variant="caption" tone="faint">
                {health.error instanceof Error ? health.error.message : 'Could not reach the server.'}
              </Text>
            </View>
          </View>
        ) : (
          <View style={styles.connected}>
            <View style={styles.statusRow}>
              <CheckCircle2 size={20} color={palette.success} />
              <View style={styles.flex}>
                <Text variant="bodyStrong" tone="success">Connected</Text>
                <Text variant="caption" tone="faint">
                  API v{health.data?.version}
                  {health.data?.ocr_available ? ' · OCR' : ''}
                  {health.data?.lsa_enabled ? ' · LSA' : ''}
                </Text>
              </View>
            </View>
            <View style={styles.divider} />
            <Text variant="caption" tone="muted">Supported formats</Text>
            <View style={styles.formats}>
              {(health.data?.supported_extensions ?? []).map((ext) => (
                <View key={ext} style={styles.formatChip}>
                  <Text variant="micro" tone="muted">{ext}</Text>
                </View>
              ))}
            </View>
          </View>
        )}
      </Card>

      {/* Sign out */}
      {user && (
        <Button
          label="Sign out"
          onPress={handleLogout}
          style={StyleSheet.flatten([styles.smallBtn, styles.signOutBtn])}
          icon={<LogOut size={18} color={palette.danger} />}
        />
      )}

      <Text variant="caption" tone="faint" style={styles.footer}>
        Doc Chat — answers are exact quotes with page citations, no AI generation.
      </Text>
    </ScrollView>
  );
}
