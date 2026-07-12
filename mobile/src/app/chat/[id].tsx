import { FlashList, type FlashListRef } from '@shopify/flash-list';
import { Stack, useLocalSearchParams, useNavigation, useRouter } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

function cleanMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')   // **bold** → bold
    .replace(/\*(.+?)\*/g, '$1')        // *italic* → italic
    .replace(/^[\*\-]\s+/gm, '• ')     // * item → • item
    .replace(/\[Passage \d+[,\s\d]*\]/g, '') // strip [Passage X] citations
    .replace(/\[Passage[^\]]*\]/g, '')
    .trim();
}
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  View,
} from 'react-native';
import { Clock, FileWarning, Loader, Sparkles, Trash2 } from 'lucide-react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useAskStream, useDeleteDocument, useDocuments, useDocumentStatus, type ChatMessage } from '@/api/hooks';
import { createSmoothStream } from '@/lib/smoothStream';
import { ChatComposer } from '@/components/ChatComposer';
import { EmptyState } from '@/components/EmptyState';
import { SegmentedControl } from '@/components/SegmentedControl';
import { StatusPill } from '@/components/StatusPill';
import { KeyPointsPanel } from '@/components/panels/KeyPointsPanel';
import { SummaryPanel } from '@/components/panels/SummaryPanel';
import { TablesPanel } from '@/components/panels/TablesPanel';
import { Text } from '@/components/ui/Text';
import { useTheme } from '@/lib/theme';
import { radius, spacing } from '@/theme/theme';

type Mode = 'chat' | 'summary' | 'keypoints' | 'tables';

const MODE_OPTIONS: { value: Mode; label: string }[] = [
  { value: 'chat', label: 'Chat' },
  { value: 'summary', label: 'Summary' },
  { value: 'keypoints', label: 'Key points' },
  { value: 'tables', label: 'Tables' },
];

type Message =
  | { kind: 'question'; id: string; text: string }
  | { kind: 'answer'; id: string; text: string }
  | { kind: 'pending'; id: string }
  | { kind: 'error'; id: string; text: string };

const SUGGESTIONS = [
  'What is this document about?',
  'What are the key findings?',
  'List the important dates',
  'What are the next steps?',
];

function MessageRow({ message }: { message: Message }) {
  const { palette } = useTheme();

  if (message.kind === 'question') {
    return (
      <View style={{ alignItems: 'flex-end' }}>
        <View
          style={{
            backgroundColor: palette.accent,
            borderRadius: radius.lg,
            borderBottomRightRadius: radius.sm,
            paddingHorizontal: spacing.lg,
            paddingVertical: spacing.md,
            maxWidth: '85%',
          }}
        >
          <Text variant="bodyStrong" style={{ color: palette.accentText }}>
            {message.text}
          </Text>
        </View>
      </View>
    );
  }

  if (message.kind === 'pending') {
    return (
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
        <View
          style={{
            width: 28,
            height: 28,
            borderRadius: 14,
            backgroundColor: palette.accentSoft,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Sparkles size={14} color={palette.accent} />
        </View>
        <View
          style={{
            backgroundColor: palette.surface,
            borderRadius: radius.lg,
            borderTopLeftRadius: radius.sm,
            borderWidth: 1,
            borderColor: palette.border,
            paddingHorizontal: spacing.lg,
            paddingVertical: spacing.md,
            flexDirection: 'row',
            alignItems: 'center',
            gap: spacing.sm,
          }}
        >
          <ActivityIndicator size="small" color={palette.accent} />
          <Text variant="caption" tone="faint">Thinking…</Text>
        </View>
      </View>
    );
  }

  if (message.kind === 'error') {
    return (
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.sm,
          backgroundColor: palette.dangerSoft,
          borderRadius: radius.md,
          padding: spacing.md,
        }}
      >
        <FileWarning size={16} color={palette.danger} />
        <Text variant="caption" tone="danger" style={{ flex: 1 }}>
          {message.text}
        </Text>
      </View>
    );
  }

  // answer
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm, maxWidth: '92%' }}>
      <View
        style={{
          width: 28,
          height: 28,
          borderRadius: 14,
          backgroundColor: palette.accentSoft,
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          marginTop: 2,
        }}
      >
        <Sparkles size={14} color={palette.accent} />
      </View>
      <View
        style={{
          flex: 1,
          backgroundColor: palette.surface,
          borderRadius: radius.lg,
          borderTopLeftRadius: radius.sm,
          borderWidth: 1,
          borderColor: palette.border,
          paddingHorizontal: spacing.lg,
          paddingVertical: spacing.md,
        }}
      >
        <Text variant="body" style={{ color: palette.text, lineHeight: 24 }}>
          {cleanMarkdown(message.text)}
        </Text>
      </View>
    </View>
  );
}

function ProcessingOrFailed({ status, error }: { status: string; error?: string | null }) {
  const { palette } = useTheme();

  if (status === 'failed') {
    return (
      <View
        style={{
          flex: 1,
          alignItems: 'center',
          justifyContent: 'center',
          paddingBottom: spacing.xxxl,
          gap: spacing.lg,
        }}
      >
        <EmptyState
          icon={<FileWarning size={40} color={palette.danger} />}
          title="Couldn't process this document"
          subtitle={error ?? 'The file could not be read. Try uploading it again.'}
        />
      </View>
    );
  }
  return (
    <View
      style={{
        flex: 1,
        alignItems: 'center',
        justifyContent: 'center',
        paddingBottom: spacing.xxxl,
        gap: spacing.lg,
      }}
    >
      <EmptyState
        icon={<Loader size={40} color={palette.accent} />}
        title="Preparing your document"
        subtitle="Extracting text and building the search index. This only takes a moment."
      />
      <View style={{ alignItems: 'center' }}>
        <StatusPill status={status === 'queued' ? 'queued' : 'processing'} />
      </View>
    </View>
  );
}

export default function ChatScreen() {
  const { id, ephemeral } = useLocalSearchParams<{ id: string; ephemeral?: string }>();
  const isEphemeral = ephemeral === 'true';
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const navigation = useNavigation();
  const { palette } = useTheme();

  const documents = useDocuments();
  const status = useDocumentStatus(id);
  const askStream = useAskStream(id);
  const del = useDeleteDocument();
  const listRef = useRef<FlashListRef<Message>>(null);
  // Prevents double-delete when the user taps the trash icon then navigates back.
  const deletedRef = useRef(false);

  const [messages, setMessages] = useState<Message[]>([]);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [mode, setMode] = useState<Mode>('chat');
  const [sending, setSending] = useState(false);

  // Auto-delete ephemeral documents when the user navigates away.
  useEffect(() => {
    if (!isEphemeral) return;
    const unsub = navigation.addListener('beforeRemove', () => {
      if (!deletedRef.current) {
        deletedRef.current = true;
        del.mutateAsync(id).catch(() => {});
      }
    });
    return unsub;
  }, [isEphemeral, navigation, id, del]);

  const doc = useMemo(
    () => documents.data?.documents.find((d) => d.id === id),
    [documents.data, id],
  );
  const currentStatus = status.data?.status ?? doc?.status ?? 'processing';
  const isReady = currentStatus === 'ready';

  const styles = useMemo(
    () =>
      StyleSheet.create({
        container: { flex: 1, backgroundColor: palette.bg },
        flex: { flex: 1 },
        segmentWrap: { paddingTop: spacing.sm },
        list: { padding: spacing.lg },
        separator: { height: spacing.lg },
        intro: { paddingTop: spacing.xxxl, gap: spacing.xl },
        suggestions: {
          flexDirection: 'row',
          flexWrap: 'wrap',
          gap: spacing.sm,
          justifyContent: 'center',
        },
        chip: {
          borderWidth: 1,
          borderColor: palette.border,
          backgroundColor: palette.surface,
          borderRadius: radius.pill,
          paddingHorizontal: spacing.lg,
          paddingVertical: spacing.sm,
        },
        chipPressed: { backgroundColor: palette.surfacePressed },
      }),
    [palette],
  );

  const send = useCallback(
    async (text: string) => {
      const qId = `q-${Date.now()}`;
      const pId = `p-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { kind: 'question', id: qId, text },
        { kind: 'pending', id: pId },
      ]);
      requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
      setSending(true);
      // Swap the "Thinking…" bubble for a live answer bubble on the first
      // chunk, then grow it as the stream continues. The smooth stream paces
      // the reveal so fast responses still visibly type out.
      const smooth = createSmoothStream((soFar) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pId ? { kind: 'answer', id: pId, text: soFar } : m,
          ),
        );
      });
      try {
        const raw = await askStream(text, history, (soFar) => smooth.push(soFar));
        const answer = await smooth.finish(raw);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pId ? { kind: 'answer', id: pId, text: answer } : m,
          ),
        );
        setHistory((prev) => [
          ...prev,
          { role: 'user', content: text },
          { role: 'model', content: answer },
        ]);
      } catch (err) {
        smooth.cancel();
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pId
              ? {
                  kind: 'error',
                  id: pId,
                  text: err instanceof Error ? err.message : 'Something went wrong.',
                }
              : m,
          ),
        );
      } finally {
        setSending(false);
      }
    },
    [askStream, history],
  );

  const confirmDelete = useCallback(() => {
    Alert.alert('Delete document?', 'This removes it and its answers.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          deletedRef.current = true;
          await del.mutateAsync(id);
          router.back();
        },
      },
    ]);
  }, [del, id, router]);

  return (
    <View style={styles.container}>
      <Stack.Screen
        options={{
          title: doc?.filename ?? 'Document',
          headerRight: () => (
            <Pressable
              onPress={confirmDelete}
              hitSlop={12}
              accessibilityLabel="Delete document"
            >
              <Trash2 size={20} color={palette.textMuted} />
            </Pressable>
          ),
        }}
      />

      {isEphemeral && (
        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            gap: spacing.sm,
            marginHorizontal: spacing.lg,
            marginBottom: spacing.xs,
            paddingHorizontal: spacing.md,
            paddingVertical: spacing.sm,
            borderRadius: 10,
            backgroundColor: palette.accentSoft,
          }}
        >
          <Clock size={14} color={palette.accent} />
          <Text variant="caption" style={{ flex: 1, color: palette.accent }}>
            Temporary — deleted automatically when you leave
          </Text>
        </View>
      )}

      {!isReady ? (
        <ProcessingOrFailed status={currentStatus} error={status.data?.error ?? doc?.error} />
      ) : (
        <View style={styles.flex}>
          <View style={styles.segmentWrap}>
            <SegmentedControl options={MODE_OPTIONS} value={mode} onChange={setMode} />
          </View>

          {mode === 'summary' ? (
            <SummaryPanel id={id} active={mode === 'summary'} />
          ) : mode === 'keypoints' ? (
            <KeyPointsPanel id={id} active={mode === 'keypoints'} />
          ) : mode === 'tables' ? (
            <TablesPanel id={id} active={mode === 'tables'} />
          ) : (
            <KeyboardAvoidingView
              style={styles.flex}
              behavior={Platform.OS === 'ios' ? 'padding' : undefined}
              keyboardVerticalOffset={90}
            >
              <FlashList
                ref={listRef}
                data={messages}
                keyExtractor={(m) => m.id}
                renderItem={({ item }) => <MessageRow message={item} />}
                contentContainerStyle={styles.list}
                ItemSeparatorComponent={() => <View style={styles.separator} />}
                keyboardDismissMode="interactive"
                onContentSizeChange={() =>
                  messages.length > 0 && listRef.current?.scrollToEnd({ animated: true })
                }
                ListEmptyComponent={
                  <View style={styles.intro}>
                    <EmptyState
                      icon={<Sparkles size={36} color={palette.accent} />}
                      title="Ask this document anything"
                      subtitle="Powered by Gemini — get clear, grounded answers from your document."
                    />
                    <View style={styles.suggestions}>
                      {SUGGESTIONS.map((s) => (
                        <Pressable
                          key={s}
                          onPress={() => send(s)}
                          style={({ pressed }) => [styles.chip, pressed && styles.chipPressed]}
                        >
                          <Text variant="caption" tone="muted">
                            {s}
                          </Text>
                        </Pressable>
                      ))}
                    </View>
                  </View>
                }
              />
              <View style={{ paddingBottom: insets.bottom + spacing.sm }}>
                <ChatComposer onSend={send} disabled={sending} />
              </View>
            </KeyboardAvoidingView>
          )}
        </View>
      )}
    </View>
  );
}
