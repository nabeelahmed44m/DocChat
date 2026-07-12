import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { ChevronDown, ChevronUp, MapPin, Quote } from 'lucide-react-native';

import type { SearchAnswer as Answer } from '@/api/types';
import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';
import { Text } from './ui/Text';

function RelevanceBar({ score, palette }: { score: number; palette: ReturnType<typeof useTheme>['palette'] }) {
  const pct = Math.max(0, Math.min(1, score));
  return (
    <View style={{ width: 48, height: 5, borderRadius: radius.pill, backgroundColor: palette.surfacePressed, overflow: 'hidden' }}>
      <View style={{ height: '100%', width: `${pct * 100}%`, backgroundColor: palette.accent, borderRadius: radius.pill }} />
    </View>
  );
}

export function AnswerCard({ answer, rank }: { answer: Answer; rank: number }) {
  const { palette } = useTheme();
  const [expanded, setExpanded] = useState(false);
  const hasContext = answer.context && answer.context !== answer.text;

  const styles = useMemo(
    () =>
      StyleSheet.create({
        card: {
          backgroundColor: palette.surface,
          borderRadius: radius.lg,
          borderWidth: 1,
          borderColor: palette.border,
          padding: spacing.lg,
          gap: spacing.sm,
        },
        topCard: {
          borderColor: palette.accentSoft,
          backgroundColor: palette.surfaceElevated,
        },
        header: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
        citationChip: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: 4,
          backgroundColor: palette.surfacePressed,
          paddingHorizontal: spacing.sm,
          paddingVertical: 3,
          borderRadius: radius.pill,
        },
        spacer: { flex: 1 },
        quote: { lineHeight: 23 },
        entities: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
        entity: {
          backgroundColor: palette.accentSoft,
          paddingHorizontal: spacing.sm,
          paddingVertical: 3,
          borderRadius: radius.sm,
        },
        context: {
          lineHeight: 20,
          borderLeftWidth: 2,
          borderLeftColor: palette.border,
          paddingLeft: spacing.md,
        },
        expandRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
      }),
    [palette],
  );

  return (
    <View style={[styles.card, rank === 0 && styles.topCard]}>
      <View style={styles.header}>
        <Quote size={16} color={palette.accent} />
        <View style={styles.citationChip}>
          <MapPin size={12} color={palette.textMuted} />
          <Text variant="micro" tone="muted">
            {answer.citation.toUpperCase()}
          </Text>
        </View>
        <View style={styles.spacer} />
        <RelevanceBar score={answer.score} palette={palette} />
      </View>

      <Text variant={rank === 0 ? 'bodyStrong' : 'body'} style={styles.quote}>
        "{answer.text}"
      </Text>

      {answer.matched_entities.length > 0 ? (
        <View style={styles.entities}>
          {answer.matched_entities.slice(0, 4).map((e, i) => (
            <View key={`${e}-${i}`} style={styles.entity}>
              <Text variant="micro" tone="accent">
                {e}
              </Text>
            </View>
          ))}
        </View>
      ) : null}

      {hasContext ? (
        <>
          {expanded ? (
            <Text variant="caption" tone="muted" style={styles.context}>
              {answer.context}
            </Text>
          ) : null}
          <Pressable
            onPress={() => setExpanded((v) => !v)}
            style={styles.expandRow}
            hitSlop={8}
          >
            <Text variant="caption" tone="faint">
              {expanded ? 'Hide context' : 'Show context'}
            </Text>
            {expanded ? (
              <ChevronUp size={14} color={palette.textFaint} />
            ) : (
              <ChevronDown size={14} color={palette.textFaint} />
            )}
          </Pressable>
        </>
      ) : null}
    </View>
  );
}
