import { useMemo } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Table2 } from 'lucide-react-native';

import { useTables } from '@/api/hooks';
import type { TableData } from '@/api/types';
import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';
import { EmptyState } from '../EmptyState';
import { QueryState } from '../QueryState';
import { Text } from '../ui/Text';

const COL_WIDTH = 130;

function TableView({
  table,
  index,
  palette,
}: {
  table: TableData;
  index: number;
  palette: ReturnType<typeof useTheme>['palette'];
}) {
  return (
    <View style={{ gap: spacing.sm }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text variant="caption" tone="muted">
          {table.title || `Table ${index + 1}`}
        </Text>
        <Text variant="micro" tone="faint">
          {table.n_rows} rows · {table.n_cols} cols
        </Text>
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator
        style={{
          borderWidth: 1,
          borderColor: palette.border,
          borderRadius: radius.md,
          backgroundColor: palette.surface,
        }}
      >
        <View>
          {/* Header row */}
          <View style={{ flexDirection: 'row', backgroundColor: palette.accentSoft }}>
            {table.header.map((cell, c) => (
              <View
                key={c}
                style={{
                  width: COL_WIDTH,
                  padding: spacing.sm,
                  borderRightWidth: StyleSheet.hairlineWidth,
                  borderBottomWidth: 1,
                  borderColor: palette.border,
                }}
              >
                <Text variant="micro" style={{ fontWeight: '700', color: palette.accent }} numberOfLines={3}>
                  {cell}
                </Text>
              </View>
            ))}
          </View>
          {/* Data rows */}
          {table.rows.map((row, r) => (
            <View
              key={r}
              style={{
                flexDirection: 'row',
                backgroundColor: r % 2 === 1 ? palette.surfacePressed : undefined,
              }}
            >
              {row.map((cell, c) => (
                <View
                  key={c}
                  style={{
                    width: COL_WIDTH,
                    padding: spacing.sm,
                    borderRightWidth: StyleSheet.hairlineWidth,
                    borderBottomWidth: StyleSheet.hairlineWidth,
                    borderColor: palette.border,
                  }}
                >
                  <Text variant="caption" numberOfLines={4}>
                    {cell}
                  </Text>
                </View>
              ))}
            </View>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

export function TablesPanel({ id, active }: { id: string; active: boolean }) {
  const { palette } = useTheme();
  const tables = useTables(id, active);

  const styles = useMemo(
    () =>
      StyleSheet.create({
        content: { padding: spacing.lg, gap: spacing.xl, paddingBottom: spacing.xxxl },
        note: {
          backgroundColor: palette.surface,
          borderRadius: radius.md,
          padding: spacing.md,
          marginBottom: spacing.xs,
        },
        empty: { flex: 1, justifyContent: 'center', paddingBottom: spacing.xxxl },
      }),
    [palette],
  );

  return (
    <QueryState
      isLoading={tables.isLoading}
      isError={tables.isError}
      error={tables.error}
      loadingLabel="Detecting tables…"
    >
      {tables.data && tables.data.count > 0 ? (
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {tables.data.note && (
            <View style={styles.note}>
              <Text variant="micro" tone="faint">
                {tables.data.note}
              </Text>
            </View>
          )}
          {tables.data.tables.map((t, i) => (
            <TableView key={i} table={t} index={i} palette={palette} />
          ))}
        </ScrollView>
      ) : (
        <View style={styles.empty}>
          <EmptyState
            icon={<Table2 size={38} color={palette.textFaint} />}
            title="No tables found"
            subtitle={tables.data?.note ?? 'No tables were detected in this document.'}
          />
        </View>
      )}
    </QueryState>
  );
}
