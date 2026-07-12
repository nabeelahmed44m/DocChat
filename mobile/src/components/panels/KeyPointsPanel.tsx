import { useMemo } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, View } from 'react-native';

import { useAnalysisStream } from '@/api/hooks';
import { parseKeypointsText } from '@/lib/analysisParse';
import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';
import { QueryState } from '../QueryState';
import { Text } from '../ui/Text';

export function KeyPointsPanel({ id, active }: { id: string; active: boolean }) {
  const { palette } = useTheme();
  const stream = useAnalysisStream(id, 'keypoints', active);
  const parsed = useMemo(() => parseKeypointsText(stream.text), [stream.text]);

  const styles = useMemo(
    () =>
      StyleSheet.create({
        content: { padding: spacing.lg, gap: spacing.xl, paddingBottom: spacing.xxxl },
        sectionLabel: { marginBottom: spacing.xs },
        labelRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
        phrases: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
        phraseChip: {
          backgroundColor: palette.surface,
          borderWidth: 1,
          borderColor: palette.border,
          paddingHorizontal: spacing.md,
          paddingVertical: spacing.xs,
          borderRadius: radius.pill,
        },
        pointRow: {
          flexDirection: 'row',
          gap: spacing.md,
          alignItems: 'flex-start',
          backgroundColor: palette.surface,
          borderRadius: radius.lg,
          padding: spacing.lg,
        },
        indexBadge: {
          width: 24,
          height: 24,
          borderRadius: 12,
          backgroundColor: palette.accentSoft,
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          marginTop: 1,
        },
        emptyText: { paddingVertical: spacing.lg },
      }),
    [palette],
  );

  return (
    <QueryState
      isLoading={stream.streaming && stream.text === ''}
      isError={stream.error !== null}
      error={stream.error ? new Error(stream.error) : undefined}
      loadingLabel="Finding key points…"
    >
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Points stream in one by one */}
        <View style={{ gap: spacing.sm }}>
          <View style={styles.labelRow}>
            <Text variant="caption" tone="muted" style={styles.sectionLabel}>
              KEY POINTS
            </Text>
            {stream.streaming ? (
              <ActivityIndicator size="small" color={palette.accent} />
            ) : null}
          </View>
          {parsed.points.length > 0 ? (
            parsed.points.map((pt, i) => (
              <View key={i} style={styles.pointRow}>
                <View style={styles.indexBadge}>
                  <Text variant="micro" tone="accent">
                    {i + 1}
                  </Text>
                </View>
                <Text variant="body" style={{ flex: 1, lineHeight: 22 }}>
                  {pt}
                </Text>
              </View>
            ))
          ) : stream.done ? (
            <Text variant="body" tone="faint" style={styles.emptyText}>
              No key points were detected in this document.
            </Text>
          ) : null}
        </View>

        {parsed.keyphrases.length > 0 && (
          <View style={{ gap: spacing.sm }}>
            <Text variant="caption" tone="muted" style={styles.sectionLabel}>
              KEY TERMS
            </Text>
            <View style={styles.phrases}>
              {parsed.keyphrases.map((phrase, i) => (
                <View key={`${phrase}-${i}`} style={styles.phraseChip}>
                  <Text variant="caption" tone="muted">
                    {phrase}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        )}
      </ScrollView>
    </QueryState>
  );
}
