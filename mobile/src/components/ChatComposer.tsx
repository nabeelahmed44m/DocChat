import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';
import { ArrowUp } from 'lucide-react-native';

import { useTheme } from '@/lib/theme';
import { radius, spacing, typography } from '@/theme/theme';

interface ChatComposerProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatComposer({
  onSend,
  disabled = false,
  placeholder = 'Ask about this document…',
}: ChatComposerProps) {
  const { palette } = useTheme();
  const [text, setText] = useState('');
  const canSend = text.trim().length > 0 && !disabled;

  const styles = useMemo(
    () =>
      StyleSheet.create({
        wrap: {
          flexDirection: 'row',
          alignItems: 'flex-end',
          gap: spacing.sm,
          paddingHorizontal: spacing.lg,
          paddingTop: spacing.sm,
        },
        input: {
          flex: 1,
          minHeight: 48,
          maxHeight: 120,
          backgroundColor: palette.surfaceElevated,
          borderRadius: radius.lg,
          borderWidth: 1,
          borderColor: palette.border,
          paddingHorizontal: spacing.lg,
          paddingTop: spacing.md,
          paddingBottom: spacing.md,
          color: palette.text,
          ...typography.body,
        },
        sendBtn: {
          width: 48,
          height: 48,
          borderRadius: radius.pill,
          backgroundColor: palette.accent,
          alignItems: 'center',
          justifyContent: 'center',
        },
        sendDisabled: { backgroundColor: palette.surfacePressed },
      }),
    [palette],
  );

  const send = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText('');
  };

  return (
    <View style={styles.wrap}>
      <TextInput
        style={styles.input}
        value={text}
        onChangeText={setText}
        placeholder={placeholder}
        placeholderTextColor={palette.textFaint}
        multiline
        onSubmitEditing={send}
        blurOnSubmit
        editable={!disabled}
        returnKeyType="send"
      />
      <Pressable
        onPress={send}
        disabled={!canSend}
        style={[styles.sendBtn, !canSend && styles.sendDisabled]}
        accessibilityRole="button"
        accessibilityLabel="Send question"
      >
        <ArrowUp size={20} color={palette.accentText} />
      </Pressable>
    </View>
  );
}
