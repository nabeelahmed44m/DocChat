import { useMemo } from 'react';
import { Pressable, StyleSheet, View, type ViewStyle } from 'react-native';

import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';

interface CardProps {
  children: React.ReactNode;
  onPress?: () => void;
  style?: ViewStyle;
  elevated?: boolean;
}

export function Card({ children, onPress, style, elevated = true }: CardProps) {
  const { palette, shadow } = useTheme();

  const styles = useMemo(
    () =>
      StyleSheet.create({
        card: {
          backgroundColor: palette.surface,
          borderRadius: radius.lg,
          borderWidth: 1,
          borderColor: palette.border,
          padding: spacing.lg,
        },
        pressed: { opacity: 0.9, transform: [{ scale: 0.99 }] },
      }),
    [palette],
  );

  const content = (
    <View style={[styles.card, elevated && shadow.card, style]}>
      {children}
    </View>
  );

  if (!onPress) return content;
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => pressed && styles.pressed}
      accessibilityRole="button"
    >
      {content}
    </Pressable>
  );
}
