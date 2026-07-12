import { FlashList } from '@shopify/flash-list';
import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, StyleSheet, View } from 'react-native';
import { FileText, MapPin, SearchX } from 'lucide-react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useSearch } from '@/api/hooks';
import type { SearchResultItem } from '@/api/types';
import { ChatComposer } from '@/components/ChatComposer';
import { EmptyState } from '@/components/EmptyState';
import { Text } from '@/components/ui/Text';
import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';

function ResultCard({ item, onPress }: { item: SearchResultItem; onPress: () => void }) {
  const { palette } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        {
          backgroundColor: palette.surface,
          borderRadius: radius.lg,
          borderWidth: 1,
          borderColor: palette.border,
          padding: spacing.lg,
          gap: spacing.sm,
        },
        pressed && { opacity: 0.9 },
      ]}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
        <FileText size={14} color={palette.accent} />
        <Text variant="caption" tone="muted" numberOfLines={1} style={{ flex: 1 }}>
          {item.filename}
        </Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: palette.surfacePressed, paddingHorizontal: spacing.sm, paddingVertical: 3, borderRadius: radius.pill }}>
          <MapPin size={11} color={palette.textFaint} />
          <Text variant="micro" tone="faint">
            {item.answer.citation.toUpperCase()}
          </Text>
        </View>
      </View>
      <Text variant="body" style={{ lineHeight: 23 }}>
        "{item.answer.text}"
      </Text>
    </Pressable>
  );
}

export default function SearchScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { palette } = useTheme();
  const search = useSearch();
  const [asked, setAsked] = useState<string | null>(null);

  const styles = useMemo(
    () =>
      StyleSheet.create({
        container: { flex: 1, backgroundColor: palette.bg },
        body: { flex: 1 },
        center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: spacing.sm },
        list: { padding: spacing.lg },
        separator: { height: spacing.md },
        resultHeader: { marginBottom: spacing.md },
      }),
    [palette],
  );

  const run = (question: string) => {
    setAsked(question);
    search.mutate(question);
  };

  const results = search.data?.results ?? [];

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={90}
    >
      <View style={styles.body}>
        {search.isPending ? (
          <View style={styles.center}>
            <ActivityIndicator size="large" color={palette.accent} />
            <Text variant="caption" tone="faint">
              Searching all documents…
            </Text>
          </View>
        ) : asked && results.length === 0 ? (
          <View style={styles.center}>
            <EmptyState
              icon={<SearchX size={38} color={palette.accent} />}
              title="No matches"
              subtitle={`Nothing relevant to "${asked}" across your ${
                search.data?.searched_documents ?? 0
              } document(s).`}
            />
          </View>
        ) : !asked ? (
          <View style={styles.center}>
            <EmptyState
              icon={<FileText size={38} color={palette.accent} />}
              title="Search across everything"
              subtitle="Ask one question and get the best-matching quote from any of your documents."
            />
          </View>
        ) : (
          <FlashList
            data={results}
            keyExtractor={(r, i) => `${r.document_id}-${i}`}
            renderItem={({ item }) => (
              <ResultCard item={item} onPress={() => router.push(`/chat/${item.document_id}`)} />
            )}
            contentContainerStyle={styles.list}
            ItemSeparatorComponent={() => <View style={styles.separator} />}
            ListHeaderComponent={
              <Text variant="caption" tone="faint" style={styles.resultHeader}>
                Best matches across {search.data?.searched_documents ?? 0} document(s)
              </Text>
            }
          />
        )}
      </View>

      <View style={{ paddingBottom: insets.bottom + spacing.sm }}>
        <ChatComposer
          onSend={run}
          disabled={search.isPending}
          placeholder="Search all documents…"
        />
      </View>
    </KeyboardAvoidingView>
  );
}
