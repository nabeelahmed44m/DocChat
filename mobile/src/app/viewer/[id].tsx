import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Platform, ScrollView, StyleSheet, View } from 'react-native';
import WebView from 'react-native-webview';

import { useDocuments } from '@/api/hooks';
import { useSettings } from '@/lib/settings';
import { useTheme } from '@/lib/theme';
import { spacing } from '@/theme/theme';
import { Text } from '@/components/ui/Text';

/**
 * Document viewer.
 *
 * PDFs, images, and Office files render in a WKWebView, which uses the
 * system's native engines — for PDFs that means the same continuous page
 * scrolling and pinch-to-zoom as Preview/Quick Look.
 *
 * Plain-text formats (.txt, .md, .csv, .log …) are fetched and rendered
 * natively instead: WKWebView shows raw text with unthemed default styling
 * that is unreadable against the app background.
 */

const TEXT_EXTENSIONS = new Set(['txt', 'text', 'md', 'markdown', 'log', 'csv']);

function extensionOf(filename: string | undefined): string {
  const dot = (filename ?? '').lastIndexOf('.');
  return dot >= 0 ? (filename ?? '').slice(dot + 1).toLowerCase() : '';
}

export default function ViewerScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { palette } = useTheme();
  const { baseUrl, apiKey } = useSettings();
  const documents = useDocuments();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [textContent, setTextContent] = useState<string | null>(null);

  const doc = useMemo(
    () => documents.data?.documents.find((d) => d.id === id),
    [documents.data, id],
  );

  const fileUrl = `${baseUrl.replace(/\/+$/, '')}/documents/${id}/file`;
  const ext = extensionOf(doc?.filename);
  const isTextFile = doc != null && TEXT_EXTENSIONS.has(ext);
  const authHeaders = useMemo(
    () => (apiKey ? { Authorization: `Bearer ${apiKey}` } : undefined),
    [apiKey],
  );

  // Text-like files: fetch the raw content and render it natively.
  useEffect(() => {
    if (!isTextFile) return;
    let cancelled = false;
    setLoading(true);
    setError(false);
    fetch(fileUrl, { headers: authHeaders })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.text();
      })
      .then((text) => {
        if (!cancelled) setTextContent(text);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isTextFile, fileUrl, authHeaders]);

  const styles = useMemo(
    () =>
      StyleSheet.create({
        container: { flex: 1, backgroundColor: palette.bg },
        webview: { flex: 1, backgroundColor: palette.bg },
        textScroll: { flex: 1 },
        textContent: { padding: spacing.lg, paddingBottom: spacing.xxxl },
        mono: {
          color: palette.text,
          fontSize: 14,
          lineHeight: 22,
          fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
        },
        overlay: {
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: palette.bg,
          gap: spacing.md,
        },
      }),
    [palette],
  );

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: doc?.filename ?? 'Document' }} />

      {isTextFile ? (
        textContent !== null && (
          <ScrollView
            style={styles.textScroll}
            contentContainerStyle={styles.textContent}
            showsVerticalScrollIndicator
          >
            <Text selectable style={styles.mono}>
              {textContent}
            </Text>
          </ScrollView>
        )
      ) : (
        <WebView
          source={{ uri: fileUrl, headers: authHeaders }}
          style={styles.webview}
          originWhitelist={['*']}
          scrollEnabled
          bounces
          showsVerticalScrollIndicator
          showsHorizontalScrollIndicator={false}
          allowsBackForwardNavigationGestures={false}
          onLoadStart={() => { setLoading(true); setError(false); }}
          onLoadEnd={() => setLoading(false)}
          onError={() => { setLoading(false); setError(true); }}
          onHttpError={(e) => {
            if (e.nativeEvent.statusCode >= 400) { setLoading(false); setError(true); }
          }}
        />
      )}

      {loading && !error && (
        <View style={styles.overlay}>
          <ActivityIndicator size="large" color={palette.accent} />
          <Text variant="caption" tone="faint">Loading document…</Text>
        </View>
      )}

      {error && (
        <View style={styles.overlay}>
          <Text variant="bodyStrong" tone="danger">Failed to load document</Text>
          <Text variant="caption" tone="faint">Check your server connection in Settings</Text>
        </View>
      )}
    </View>
  );
}
