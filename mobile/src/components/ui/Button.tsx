import { useMemo } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View, type ViewStyle } from 'react-native';

import { useTheme } from '@/lib/theme';
import { radius, spacing, typography } from '@/theme/theme';
import { Text } from './Text';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface ButtonProps {
  label: string;
  onPress: () => void;
  variant?: Variant;
  icon?: React.ReactNode;
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
}

export function Button({
  label,
  onPress,
  variant = 'primary',
  icon,
  loading = false,
  disabled = false,
  style,
}: ButtonProps) {
  const { palette } = useTheme();
  const isDisabled = disabled || loading;

  const bg: Record<Variant, string> = {
    primary: palette.accent,
    secondary: palette.surfaceElevated,
    ghost: 'transparent',
    danger: palette.dangerSoft,
  };

  const fg: Record<Variant, string> = {
    primary: palette.accentText,
    secondary: palette.text,
    ghost: palette.textMuted,
    danger: palette.danger,
  };

  const styles = useMemo(
    () =>
      StyleSheet.create({
        base: {
          minHeight: 52,
          borderRadius: radius.md,
          paddingHorizontal: spacing.xl,
          alignItems: 'center',
          justifyContent: 'center',
        },
        ghostBorder: { borderWidth: 1, borderColor: palette.border },
        content: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
        pressed: { opacity: 0.85, transform: [{ scale: 0.98 }] },
        disabled: { opacity: 0.5 },
      }),
    [palette],
  );

  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.base,
        { backgroundColor: bg[variant] },
        variant === 'ghost' && styles.ghostBorder,
        pressed && !isDisabled && styles.pressed,
        isDisabled && styles.disabled,
        style,
      ]}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      {loading ? (
        <ActivityIndicator color={fg[variant]} />
      ) : (
        <View style={styles.content}>
          {icon}
          <Text style={[typography.bodyStrong, { color: fg[variant] }]}>
            {label}
          </Text>
        </View>
      )}
    </Pressable>
  );
}
