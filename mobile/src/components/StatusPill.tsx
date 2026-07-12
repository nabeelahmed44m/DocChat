import { ActivityIndicator, StyleSheet, View } from 'react-native';

import type { DocumentStatus } from '@/api/types';
import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';
import { Text } from './ui/Text';

export function StatusPill({ status }: { status: DocumentStatus }) {
  const { palette } = useTheme();

  const config: Record<DocumentStatus, { label: string; color: string; soft: string }> = {
    queued: { label: 'Queued', color: palette.info, soft: palette.infoSoft },
    processing: { label: 'Processing', color: palette.warning, soft: palette.warningSoft },
    ready: { label: 'Ready', color: palette.success, soft: palette.successSoft },
    failed: { label: 'Failed', color: palette.danger, soft: palette.dangerSoft },
  };

  const { label, color, soft } = config[status];
  return (
    <View style={[styles.pill, { backgroundColor: soft }]}>
      {status === 'processing' ? (
        <ActivityIndicator size="small" color={color} />
      ) : (
        <View style={[styles.dot, { backgroundColor: color }]} />
      )}
      <Text variant="caption" style={{ color, fontSize: 12 }}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs + 2,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.pill,
    alignSelf: 'flex-start',
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
});
