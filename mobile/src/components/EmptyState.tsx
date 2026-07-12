import { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';
import { Text } from './ui/Text';

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, subtitle, action }: EmptyStateProps) {
  const { palette } = useTheme();

  const styles = useMemo(
    () =>
      StyleSheet.create({
        wrap: { alignItems: 'center', paddingHorizontal: spacing.xl, gap: spacing.sm },
        iconRing: {
          width: 88,
          height: 88,
          borderRadius: radius.pill,
          backgroundColor: palette.accentSoft,
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: spacing.md,
        },
        title: { textAlign: 'center' },
        subtitle: { textAlign: 'center', lineHeight: 22 },
        action: { marginTop: spacing.lg, alignSelf: 'stretch' },
      }),
    [palette],
  );

  return (
    <View style={styles.wrap}>
      <View style={styles.iconRing}>{icon}</View>
      <Text variant="heading" style={styles.title}>
        {title}
      </Text>
      {subtitle ? (
        <Text variant="body" tone="muted" style={styles.subtitle}>
          {subtitle}
        </Text>
      ) : null}
      {action ? <View style={styles.action}>{action}</View> : null}
    </View>
  );
}
