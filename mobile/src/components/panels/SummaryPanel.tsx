import { useMemo } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, View } from 'react-native';

import { useAnalysisStream } from '@/api/hooks';
import { parseSummaryText } from '@/lib/analysisParse';
import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';
import { QueryState } from '../QueryState';
import { Text } from '../ui/Text';

export function SummaryPanel({ id, active }: { id: string; active: boolean }) {
  const { palette } = useTheme();
  const stream = useAnalysisStream(id, 'summary', active);
  const parsed = useMemo(() => parseSummaryText(stream.text), [stream.text]);

  const styles = useMemo(
    () =>
      StyleSheet.create({
        content: { padding: spacing.lg, gap: spacing.xl, paddingBottom: spacing.xxxl },
        summaryCard: {
          backgroundColor: palette.surface,
          borderRadius: radius.lg,
          padding: spacing.lg,
          gap: spacing.sm,
        },
        sectionLabel: { marginBottom: spacing.xs },
        labelRow: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.sm,
        },
        bullet: { flexDirection: 'row', gap: spacing.md, alignItems: 'flex-start' },
        dot: {
          width: 7,
          height: 7,
          borderRadius: 4,
          backgroundColor: palette.accent,
          marginTop: 7,
          flexShrink: 0,
        },
      }),
    [palette],
  );

  return (
    <QueryState
      isLoading={stream.streaming && stream.text === ''}
      isError={stream.error !== null}
      error={stream.error ? new Error(stream.error) : undefined}
      loadingLabel="Summarizing…"
    >
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Prose summary — grows live while the stream is in flight */}
        <View style={styles.summaryCard}>
          <View style={styles.labelRow}>
            <Text variant="caption" tone="accent" style={styles.sectionLabel}>
              OVERVIEW
            </Text>
            {stream.streaming ? (
              <ActivityIndicator size="small" color={palette.accent} />
            ) : null}
          </View>
          <Text variant="body" style={{ lineHeight: 24 }}>
            {parsed.summary}
          </Text>
        </View>

        {/* Bullet points appear one by one as they stream in */}
        {parsed.bulletPoints.length > 0 && (
          <View style={{ gap: spacing.sm }}>
            <Text variant="caption" tone="muted" style={styles.sectionLabel}>
              HIGHLIGHTS
            </Text>
            {parsed.bulletPoints.map((pt, i) => (
              <View key={i} style={styles.bullet}>
                <View style={styles.dot} />
                <Text variant="body" style={{ flex: 1, lineHeight: 22 }}>
                  {pt}
                </Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </QueryState>
  );
}
