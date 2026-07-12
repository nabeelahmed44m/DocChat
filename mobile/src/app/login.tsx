import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from 'react-native';
import { Lock, Mail } from 'lucide-react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Text } from '@/components/ui/Text';
import { useAuth } from '@/lib/auth';
import { useTheme } from '@/lib/theme';
import { radius, spacing, typography } from '@/theme/theme';

export default function LoginScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { login } = useAuth();
  const { palette } = useTheme();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const styles = useMemo(
    () =>
      StyleSheet.create({
        root: { flex: 1, backgroundColor: palette.bg },
        container: { padding: spacing.lg, paddingBottom: spacing.xxxl },
        hero: { gap: spacing.xs, marginBottom: spacing.xl },
        card: { gap: 0 },
        inputRow: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.sm,
          paddingVertical: spacing.md,
        },
        divider: { height: 1, backgroundColor: palette.border },
        input: { flex: 1, color: palette.text, ...typography.body },
        btn: { marginTop: spacing.lg },
        footer: { alignItems: 'center', marginTop: spacing.xl },
      }),
    [palette],
  );

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      Alert.alert('Missing fields', 'Please enter your email and password.');
      return;
    }
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      router.replace('/');
    } catch (err) {
      Alert.alert('Login failed', err instanceof Error ? err.message : 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={[styles.container, { paddingTop: insets.top + spacing.xxxl }]}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.hero}>
          <Text variant="display">Gist</Text>
          <Text variant="body" tone="muted">
            Sign in to talk to your documents
          </Text>
        </View>

        <Card style={styles.card}>
          <View style={styles.inputRow}>
            <Mail size={18} color={palette.textMuted} />
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="Email"
              placeholderTextColor={palette.textFaint}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              textContentType="emailAddress"
            />
          </View>
          <View style={styles.divider} />
          <View style={styles.inputRow}>
            <Lock size={18} color={palette.textMuted} />
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="Password"
              placeholderTextColor={palette.textFaint}
              secureTextEntry
              textContentType="password"
              onSubmitEditing={handleLogin}
              returnKeyType="go"
            />
          </View>
        </Card>

        <Button
          label={loading ? 'Signing in…' : 'Sign in'}
          onPress={handleLogin}
          disabled={loading}
          style={styles.btn}
        />

        <Pressable onPress={() => router.replace('/signup')} style={styles.footer}>
          <Text variant="caption" tone="muted">
            Don't have an account?{' '}
            <Text variant="caption" tone="accent">
              Sign up
            </Text>
          </Text>
        </Pressable>

        <Pressable onPress={() => router.replace('/')} style={[styles.footer, { marginTop: spacing.sm }]}>
          <Text variant="caption" tone="faint">
            Continue without signing in
          </Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
