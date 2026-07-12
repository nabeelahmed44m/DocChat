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
import { Lock, Mail, User } from 'lucide-react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Text } from '@/components/ui/Text';
import { useAuth } from '@/lib/auth';
import { useTheme } from '@/lib/theme';
import { spacing, typography } from '@/theme/theme';

export default function SignupScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { register } = useAuth();
  const { palette } = useTheme();
  const [name, setName] = useState('');
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

  const handleSignup = async () => {
    if (!name.trim() || !email.trim() || !password) {
      Alert.alert('Missing fields', 'Please fill in all fields.');
      return;
    }
    if (password.length < 6) {
      Alert.alert('Weak password', 'Password must be at least 6 characters.');
      return;
    }
    setLoading(true);
    try {
      await register(email.trim().toLowerCase(), name.trim(), password);
      router.replace('/');
    } catch (err) {
      Alert.alert('Sign up failed', err instanceof Error ? err.message : 'Something went wrong.');
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
          <Text variant="display">Create account</Text>
          <Text variant="body" tone="muted">
            Sign up to save and chat with your documents
          </Text>
        </View>

        <Card style={styles.card}>
          <View style={styles.inputRow}>
            <User size={18} color={palette.textMuted} />
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="Full name"
              placeholderTextColor={palette.textFaint}
              autoCorrect={false}
              textContentType="name"
            />
          </View>
          <View style={styles.divider} />
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
              placeholder="Password (min 6 characters)"
              placeholderTextColor={palette.textFaint}
              secureTextEntry
              textContentType="newPassword"
              onSubmitEditing={handleSignup}
              returnKeyType="go"
            />
          </View>
        </Card>

        <Button
          label={loading ? 'Creating account…' : 'Create account'}
          onPress={handleSignup}
          disabled={loading}
          style={styles.btn}
        />

        <Pressable onPress={() => router.replace('/login')} style={styles.footer}>
          <Text variant="caption" tone="muted">
            Already have an account?{' '}
            <Text variant="caption" tone="accent">
              Sign in
            </Text>
          </Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
