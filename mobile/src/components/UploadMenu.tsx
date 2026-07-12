/**
 * Bottom sheet for choosing how to add a document.
 *
 * Auth rules:
 *  - "Choose a file" → always available (even anonymous — ephemeral usage)
 *  - "Scan / Photo" → requires login (camera/photos need user context)
 *  - "Save to library" toggle → if toggled ON while logged out, redirects to login
 *
 * Picker bug fix: we use `onDismiss` (iOS) + a 350ms fallback to ensure the
 * modal is fully gone before the native document/image picker opens. Calling a
 * system picker while a modal sheet is still animating throws
 * "Different document picking in progress".
 */

import { useRouter } from 'expo-router';
import { useMemo, useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, Switch, View } from 'react-native';
import { Camera, FileUp, ImageIcon, Lock, Save, X } from 'lucide-react-native';

import { useAuth } from '@/lib/auth';
import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';
import { Text } from './ui/Text';

export type UploadSource = 'file' | 'photo' | 'camera';

interface UploadMenuProps {
  visible: boolean;
  onClose: () => void;
  onSelect: (source: UploadSource, persist: boolean) => void;
}

export function UploadMenu({ visible, onClose, onSelect }: UploadMenuProps) {
  const router = useRouter();
  const { user } = useAuth();
  const { palette } = useTheme();
  const [persist, setPersist] = useState(false);
  const pendingRef = useRef<{ source: UploadSource; persist: boolean } | null>(null);

  const styles = useMemo(
    () =>
      StyleSheet.create({
        backdrop: {
          flex: 1,
          backgroundColor: 'rgba(0,0,0,0.6)',
          justifyContent: 'flex-end',
        },
        sheet: {
          backgroundColor: palette.surfaceElevated,
          borderTopLeftRadius: radius.xl,
          borderTopRightRadius: radius.xl,
          padding: spacing.xl,
          paddingBottom: spacing.xxxl,
          gap: spacing.sm,
        },
        handle: {
          width: 40,
          height: 4,
          borderRadius: radius.pill,
          backgroundColor: palette.border,
          alignSelf: 'center',
          marginBottom: spacing.md,
        },
        header: {
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: spacing.sm,
        },
        row: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.md,
          paddingVertical: spacing.md,
          paddingHorizontal: spacing.sm,
          borderRadius: radius.md,
        },
        rowPressed: { backgroundColor: palette.surfacePressed },
        rowIcon: {
          width: 44,
          height: 44,
          borderRadius: radius.md,
          backgroundColor: palette.accentSoft,
          alignItems: 'center',
          justifyContent: 'center',
        },
        rowText: { flex: 1, gap: 2 },
        saveRow: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.md,
          paddingVertical: spacing.md,
          paddingHorizontal: spacing.sm,
          marginTop: spacing.sm,
          borderTopWidth: 1,
          borderTopColor: palette.border,
        },
      }),
    [palette],
  );

  const handleDismissed = () => {
    if (pendingRef.current) {
      const { source, persist: p } = pendingRef.current;
      pendingRef.current = null;
      onSelect(source, p);
    }
  };

  const pick = (source: UploadSource) => {
    if ((source === 'camera' || source === 'photo') && !user) {
      onClose();
      setTimeout(() => router.push('/login'), 350);
      return;
    }
    if (persist && !user) {
      onClose();
      setTimeout(() => router.push('/login'), 350);
      return;
    }
    pendingRef.current = { source, persist };
    onClose();
  };

  const handleSaveToggle = (val: boolean) => {
    if (val && !user) {
      onClose();
      setTimeout(() => router.push('/login'), 350);
      return;
    }
    setPersist(val);
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      onDismiss={handleDismissed}
    >
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.handle} />
          <View style={styles.header}>
            <Text variant="heading">Add a document</Text>
            <Pressable onPress={onClose} hitSlop={12} accessibilityLabel="Close">
              <X size={22} color={palette.textMuted} />
            </Pressable>
          </View>

          <Pressable
            onPress={() => pick('file')}
            style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
            accessibilityRole="button"
          >
            <View style={styles.rowIcon}>
              <FileUp size={22} color={palette.accent} />
            </View>
            <View style={styles.rowText}>
              <Text variant="bodyStrong">Choose a file</Text>
              <Text variant="caption" tone="faint">
                PDF, Word, or text from Files, Drive, iCloud
              </Text>
            </View>
          </Pressable>

          <Pressable
            onPress={() => pick('camera')}
            style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
            accessibilityRole="button"
          >
            <View style={styles.rowIcon}>
              <Camera size={22} color={user ? palette.accent : palette.textFaint} />
            </View>
            <View style={styles.rowText}>
              <Text variant="bodyStrong" tone={user ? 'default' : 'faint'}>
                Scan with camera
              </Text>
              <Text variant="caption" tone="faint">
                {user ? 'Photograph a paper document — read via OCR' : 'Sign in to use camera'}
              </Text>
            </View>
            {!user && <Lock size={16} color={palette.textFaint} />}
          </Pressable>

          <Pressable
            onPress={() => pick('photo')}
            style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
            accessibilityRole="button"
          >
            <View style={styles.rowIcon}>
              <ImageIcon size={22} color={user ? palette.accent : palette.textFaint} />
            </View>
            <View style={styles.rowText}>
              <Text variant="bodyStrong" tone={user ? 'default' : 'faint'}>
                Pick a photo
              </Text>
              <Text variant="caption" tone="faint">
                {user ? 'Use an existing image of a document' : 'Sign in to use gallery'}
              </Text>
            </View>
            {!user && <Lock size={16} color={palette.textFaint} />}
          </Pressable>

          <View style={styles.saveRow}>
            <View style={styles.rowIcon}>
              <Save size={20} color={palette.accent} />
            </View>
            <View style={styles.rowText}>
              <Text variant="bodyStrong">Save to my library</Text>
              <Text variant="caption" tone="faint">
                {persist
                  ? 'Saved to your library — reopen anytime.'
                  : user
                    ? 'Temporary — deleted automatically when you leave the chat.'
                    : 'Sign in to save documents to your library.'}
              </Text>
            </View>
            <Switch
              value={persist}
              onValueChange={handleSaveToggle}
              trackColor={{ true: palette.accent, false: palette.surfacePressed }}
              thumbColor={palette.text}
              accessibilityLabel="Save to my library"
            />
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
