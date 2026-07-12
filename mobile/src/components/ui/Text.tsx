import { Text as RNText, type TextProps as RNTextProps } from 'react-native';

import { useTheme } from '@/lib/theme';
import { typography } from '@/theme/theme';

type Variant = keyof typeof typography;
type Tone = 'default' | 'muted' | 'faint' | 'accent' | 'danger' | 'success';

export interface TextProps extends RNTextProps {
  variant?: Variant;
  tone?: Tone;
}

export function Text({
  variant = 'body',
  tone = 'default',
  style,
  ...rest
}: TextProps) {
  const { palette } = useTheme();

  const toneColor: Record<Tone, string> = {
    default: palette.text,
    muted: palette.textMuted,
    faint: palette.textFaint,
    accent: palette.accent,
    danger: palette.danger,
    success: palette.success,
  };

  return (
    <RNText
      style={[typography[variant], { color: toneColor[tone] }, style]}
      {...rest}
    />
  );
}
