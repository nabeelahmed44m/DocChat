import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { AlertTriangle } from 'lucide-react-native';

import { useTheme } from '@/lib/theme';
import { spacing } from '@/theme/theme';
import { Text } from './ui/Text';

interface QueryStateProps {
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  loadingLabel?: string;
  children: React.ReactNode;
}

export function QueryState({
  isLoading,
  isError,
  error,
  loadingLabel = 'Loading…',
  children,
}: QueryStateProps) {
  const { palette } = useTheme();

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={palette.accent} />
        <Text variant="caption" tone="faint">
          {loadingLabel}
        </Text>
      </View>
    );
  }
  if (isError) {
    return (
      <View style={styles.center}>
        <AlertTriangle size={28} color={palette.danger} />
        <Text variant="body" tone="danger">
          Couldn't load this
        </Text>
        <Text variant="caption" tone="faint" style={styles.errorText}>
          {error instanceof Error ? error.message : 'Please try again.'}
        </Text>
      </View>
    );
  }
  return <>{children}</>;
}

const styles = StyleSheet.create({
  center: {
    paddingVertical: spacing.xxxl,
    alignItems: 'center',
    gap: spacing.sm,
  },
  errorText: { textAlign: 'center', paddingHorizontal: spacing.xl },
});
