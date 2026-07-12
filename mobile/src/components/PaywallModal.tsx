/**
 * Shown when a user tries to upload a file larger than the free-tier limit.
 * Opens Stripe Checkout in Safari via expo-web-browser so the app never
 * handles payment data directly (and stays within App Store guidelines).
 */

import * as WebBrowser from 'expo-web-browser';
import { useRouter } from 'expo-router';
import { useMemo } from 'react';
import { Alert, Modal, Pressable, StyleSheet, View } from 'react-native';
import { Check, Crown, FileUp, Zap } from 'lucide-react-native';
import { useQueryClient } from '@tanstack/react-query';

import { useCreateCheckout } from '@/api/hooks';
import { useAuth } from '@/lib/auth';
import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';
import { Text } from './ui/Text';
import { Button } from './ui/Button';

const FREE_LIMIT_MB = 1;
const PRO_LIMIT_MB = 50;
const PRO_PRICE = '$4.99 / month';

const PRO_FEATURES = [
  `Documents up to ${PRO_LIMIT_MB} MB`,
  'Unlimited uploads',
  'AI chat, summary & key points',
  'Cross-document search',
];

interface PaywallModalProps {
  visible: boolean;
  fileSizeBytes?: number;
  onClose: () => void;
  /** Called after successful payment so the caller can retry the upload. */
  onUpgraded: () => void;
}

export function PaywallModal({ visible, fileSizeBytes, onClose, onUpgraded }: PaywallModalProps) {
  const { palette } = useTheme();
  const { user } = useAuth();
  const router = useRouter();
  const checkout = useCreateCheckout();
  const qc = useQueryClient();

  const fileMB = fileSizeBytes ? (fileSizeBytes / (1024 * 1024)).toFixed(1) : null;

  const styles = useMemo(
    () =>
      StyleSheet.create({
        backdrop: {
          flex: 1,
          backgroundColor: 'rgba(0,0,0,0.65)',
          justifyContent: 'flex-end',
        },
        sheet: {
          backgroundColor: palette.surfaceElevated,
          borderTopLeftRadius: radius.xl,
          borderTopRightRadius: radius.xl,
          padding: spacing.xl,
          paddingBottom: spacing.xxxl,
          gap: spacing.lg,
        },
        handle: {
          width: 40,
          height: 4,
          borderRadius: radius.pill,
          backgroundColor: palette.border,
          alignSelf: 'center',
          marginBottom: spacing.sm,
        },
        header: {
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        },
        crownBadge: {
          width: 44,
          height: 44,
          borderRadius: radius.lg,
          backgroundColor: palette.accentSoft,
          alignItems: 'center',
          justifyContent: 'center',
        },
        tierRow: {
          flexDirection: 'row',
          gap: spacing.sm,
        },
        tierCard: {
          flex: 1,
          borderRadius: radius.lg,
          borderWidth: 1,
          padding: spacing.md,
          gap: spacing.xs,
        },
        featureRow: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.sm,
        },
      }),
    [palette],
  );

  const handleUpgrade = async () => {
    if (!user) {
      onClose();
      setTimeout(() => router.push('/login'), 300);
      return;
    }
    try {
      const { url } = await checkout.mutateAsync();
      const result = await WebBrowser.openAuthSessionAsync(url, 'gist://billing');
      if (result.type === 'success') {
        // Refresh billing status then tell parent to retry
        await qc.invalidateQueries({ queryKey: ['billing'] });
        onUpgraded();
      }
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'Could not open checkout.');
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.handle} />

          {/* Header */}
          <View style={styles.header}>
            <View style={{ flex: 1, gap: spacing.xs }}>
              <Text variant="heading">Upgrade to Pro</Text>
              {fileMB ? (
                <Text variant="caption" tone="faint">
                  This file is {fileMB} MB — free plan is limited to {FREE_LIMIT_MB} MB.
                </Text>
              ) : (
                <Text variant="caption" tone="faint">
                  Unlock larger documents and unlimited uploads.
                </Text>
              )}
            </View>
            <View style={styles.crownBadge}>
              <Crown size={22} color={palette.accent} />
            </View>
          </View>

          {/* Tier comparison */}
          <View style={styles.tierRow}>
            {/* Free */}
            <View style={[styles.tierCard, { borderColor: palette.border, backgroundColor: palette.surface }]}>
              <Text variant="caption" tone="muted">FREE</Text>
              <Text variant="bodyStrong">$0</Text>
              <Text variant="micro" tone="faint">Up to {FREE_LIMIT_MB} MB per file</Text>
            </View>
            {/* Pro */}
            <View style={[styles.tierCard, { borderColor: palette.accent, backgroundColor: palette.accentSoft }]}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                <Zap size={12} color={palette.accent} />
                <Text variant="caption" style={{ color: palette.accent }}>PRO</Text>
              </View>
              <Text variant="bodyStrong">{PRO_PRICE}</Text>
              <Text variant="micro" tone="faint">Up to {PRO_LIMIT_MB} MB per file</Text>
            </View>
          </View>

          {/* Pro feature list */}
          <View style={{ gap: spacing.sm }}>
            {PRO_FEATURES.map((f) => (
              <View key={f} style={styles.featureRow}>
                <Check size={15} color={palette.accent} />
                <Text variant="body">{f}</Text>
              </View>
            ))}
          </View>

          {/* CTA */}
          <Button
            label={checkout.isPending ? 'Opening checkout…' : `Upgrade — ${PRO_PRICE}`}
            onPress={handleUpgrade}
            disabled={checkout.isPending}
            icon={<FileUp size={18} color={palette.accentText} />}
          />

          <Pressable onPress={onClose} style={{ alignItems: 'center' }} hitSlop={12}>
            <Text variant="caption" tone="faint">Maybe later</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
