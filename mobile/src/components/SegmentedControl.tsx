import { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';
import { Text } from './ui/Text';

interface SegmentedControlProps<T extends string> {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: SegmentedControlProps<T>) {
  const { palette } = useTheme();

  const styles = useMemo(
    () =>
      StyleSheet.create({
        track: {
          flexDirection: 'row',
          backgroundColor: palette.surface,
          borderRadius: radius.md,
          borderWidth: 1,
          borderColor: palette.border,
          padding: 3,
          marginHorizontal: spacing.lg,
          marginBottom: spacing.md,
        },
        segment: {
          flex: 1,
          paddingVertical: spacing.sm,
          alignItems: 'center',
          borderRadius: radius.sm,
        },
        segmentActive: { backgroundColor: palette.surfacePressed },
        activeLabel: { fontWeight: '700' },
      }),
    [palette],
  );

  return (
    <View style={styles.track}>
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <Pressable
            key={opt.value}
            onPress={() => onChange(opt.value)}
            style={[styles.segment, active && styles.segmentActive]}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
          >
            <Text
              variant="caption"
              tone={active ? 'default' : 'muted'}
              style={active ? styles.activeLabel : undefined}
            >
              {opt.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
