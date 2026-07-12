import { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Eye } from 'lucide-react-native';

import type { DocumentRecord } from '@/api/types';
import { fileKind, formatBytes, relativeTime } from '@/lib/format';
import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';
import { Text } from './ui/Text';
import { StatusPill } from './StatusPill';

// Per-type badge text colour, shown on a translucent pill over the pastel card.
const KIND_COLOR = {
  PDF: '#5645D4',
  XLSX: '#16A34A',
  DOCX: '#2563EB',
  IMAGE: '#D97706',
  CSV: '#16A34A',
  PPTX: '#DC2626',
  TXT: '#5E5C58',
} as const;

function kindColor(kind: string, fallback: string): string {
  return KIND_COLOR[kind as keyof typeof KIND_COLOR] ?? fallback;
}

export function DocumentCard({
  doc,
  index,
  onPress,
  onView,
}: {
  doc: DocumentRecord;
  /** Position in the list — picks the pastel tint, rotating through the palette. */
  index: number;
  onPress: () => void;
  onView?: () => void;
}) {
  const { palette, isDark } = useTheme();
  const kind = fileKind(doc.filename);
  const pages = doc.stats?.pages;
  const isReady = doc.status === 'ready';
  const tint = palette.cardTints[index % palette.cardTints.length];
  const badgeColor = isDark ? palette.text : kindColor(kind, palette.textMuted);
  const pillBg = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.72)';

  const styles = useMemo(
    () =>
      StyleSheet.create({
        card: {
          borderRadius: radius.xl,
          backgroundColor: tint,
          padding: spacing.lg,
          gap: spacing.sm,
          borderWidth: isDark ? 1 : 0,
          borderColor: palette.border,
        },
        topRow: {
          flexDirection: 'row',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: spacing.sm,
        },
        filename: { flex: 1, paddingTop: 2 },
        badge: {
          backgroundColor: pillBg,
          paddingHorizontal: spacing.md,
          paddingVertical: 4,
          borderRadius: radius.pill,
        },
        bottomRow: {
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginTop: spacing.xs,
        },
        rowGroup: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
        eyeBtn: {
          width: 32,
          height: 32,
          borderRadius: 16,
          backgroundColor: pillBg,
          alignItems: 'center',
          justifyContent: 'center',
        },
      }),
    [palette, tint, pillBg, isDark],
  );

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && { opacity: 0.8 }]}
    >
      {/* Top: filename + type badge */}
      <View style={styles.topRow}>
        <Text variant="bodyStrong" numberOfLines={1} style={styles.filename}>
          {doc.filename}
        </Text>
        <View style={styles.badge}>
          <Text variant="micro" style={{ color: badgeColor }}>
            {kind}
          </Text>
        </View>
      </View>

      {/* Meta: size · pages */}
      <Text variant="caption" tone="muted">
        {formatBytes(doc.size_bytes)}
        {isReady && pages ? ` · ${pages} page${pages !== 1 ? 's' : ''}` : ''}
      </Text>

      {/* Bottom: status pill + time + view button */}
      <View style={styles.bottomRow}>
        <View style={styles.rowGroup}>
          <StatusPill status={doc.status} />
          {doc.status === 'failed' && doc.error ? (
            <Text variant="micro" tone="danger" numberOfLines={1} style={{ flex: 1 }}>
              {doc.error}
            </Text>
          ) : null}
        </View>
        <View style={styles.rowGroup}>
          <Text variant="micro" tone="faint">
            {relativeTime(doc.created_at)}
          </Text>
          {onView && isReady ? (
            <Pressable
              onPress={(e) => { e.stopPropagation?.(); onView(); }}
              hitSlop={8}
              style={({ pressed }) => [styles.eyeBtn, pressed && { opacity: 0.6 }]}
              accessibilityLabel="View document"
            >
              <Eye size={15} color={palette.textMuted} />
            </Pressable>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}
