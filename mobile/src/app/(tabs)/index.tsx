import { FlashList } from '@shopify/flash-list';
import { useRouter } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { Alert, Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import { FileStack, Plus, Search, Settings2, WifiOff } from 'lucide-react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useDocuments, useHealth, useUploadDocument } from '@/api/hooks';
import { DocumentCard } from '@/components/DocumentCard';
import { EmptyState } from '@/components/EmptyState';
import { UploadMenu, type UploadSource } from '@/components/UploadMenu';
import { Button } from '@/components/ui/Button';
import { Text } from '@/components/ui/Text';
import { pickDocument, pickImage, scanWithCamera } from '@/lib/pick';
import { useTheme } from '@/lib/theme';
import { spacing } from '@/theme/theme';

export default function DocumentsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { palette, shadow } = useTheme();
  const documents = useDocuments();
  const health = useHealth();
  const upload = useUploadDocument();
  const [menuOpen, setMenuOpen] = useState(false);

  const styles = useMemo(
    () =>
      StyleSheet.create({
        container: { flex: 1, backgroundColor: palette.bg },
        header: {
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          paddingHorizontal: spacing.lg,
          marginBottom: spacing.lg,
        },
        headerText: { flex: 1, gap: spacing.xs },
        headerActions: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
        settingsBtn: {
          width: 40,
          height: 40,
          borderRadius: 20,
          backgroundColor: palette.surface,
          borderWidth: 1,
          borderColor: palette.border,
          alignItems: 'center',
          justifyContent: 'center',
        },
        banner: {
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.sm,
          marginHorizontal: spacing.lg,
          marginBottom: spacing.md,
          padding: spacing.md,
          borderRadius: 12,
          backgroundColor: palette.dangerSoft,
        },
        bannerText: { flex: 1 },
        list: { paddingHorizontal: spacing.lg, paddingBottom: 120 },
        separator: { height: spacing.md },
        empty: { marginTop: spacing.xxxl * 1.5 },
        fab: {
          position: 'absolute',
          right: spacing.lg,
          width: 60,
          height: 60,
          borderRadius: 30,
          backgroundColor: palette.accent,
          alignItems: 'center',
          justifyContent: 'center',
        },
      }),
    [palette],
  );

  const handleSelect = useCallback(
    async (source: UploadSource, persist: boolean) => {
      try {
        const picker =
          source === 'file' ? pickDocument : source === 'camera' ? scanWithCamera : pickImage;
        const file = await picker();
        if (!file) return;
        const record = await upload.mutateAsync({ file, persist });
        // Ephemeral uploads skip the library and go straight to chat.
        // The chat screen will delete the document when the user leaves.
        if (!persist) {
          router.push(`/chat/${record.id}?ephemeral=true`);
        }
      } catch (err) {
        Alert.alert(
          'Upload failed',
          err instanceof Error ? err.message : 'Something went wrong.',
        );
      }
    },
    [upload, router],
  );

  const docs = documents.data?.documents ?? [];
  const disconnected = health.isError;

  return (
    <View style={[styles.container, { paddingTop: insets.top + spacing.sm }]}>
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text variant="display">Documents</Text>
          <Text variant="caption" tone="muted">
            Upload, then ask anything — answers cite the page.
          </Text>
        </View>
        <View style={styles.headerActions}>
          <Pressable
            onPress={() => router.push('/search')}
            hitSlop={12}
            style={styles.settingsBtn}
            accessibilityLabel="Search all documents"
          >
            <Search size={19} color={palette.textMuted} />
          </Pressable>
          <Pressable
            onPress={() => router.push('/settings')}
            hitSlop={12}
            style={styles.settingsBtn}
            accessibilityLabel="Settings"
          >
            <Settings2 size={19} color={palette.textMuted} />
          </Pressable>
        </View>
      </View>

      {disconnected ? (
        <Pressable onPress={() => router.push('/settings')} style={styles.banner}>
          <WifiOff size={16} color={palette.danger} />
          <Text variant="caption" tone="danger" style={styles.bannerText}>
            Can't reach the server. Tap to set the address.
          </Text>
        </Pressable>
      ) : null}

      <FlashList
        data={docs}
        keyExtractor={(item) => item.id}
        renderItem={({ item, index }) => (
          <DocumentCard
            doc={item}
            index={index}
            onPress={() => router.push(`/chat/${item.id}`)}
            onView={() => router.push(`/viewer/${item.id}`)}
          />
        )}
        contentContainerStyle={styles.list}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={documents.isFetching && !documents.isLoading}
            onRefresh={() => documents.refetch()}
            tintColor={palette.accent}
          />
        }
        ListEmptyComponent={
          documents.isLoading ? null : (
            <View style={styles.empty}>
              <EmptyState
                icon={<FileStack size={40} color={palette.accent} />}
                title="No documents yet"
                subtitle="Add a contract, report, or manual and start asking questions about it."
                action={
                  <Button
                    label="Add your first document"
                    onPress={() => setMenuOpen(true)}
                    icon={<Plus size={20} color={palette.accentText} />}
                  />
                }
              />
            </View>
          )
        }
      />

      {docs.length > 0 ? (
        <Pressable
          onPress={() => setMenuOpen(true)}
          style={[styles.fab, shadow.floating, { bottom: spacing.xl }]}
          accessibilityLabel="Add document"
        >
          <Plus size={26} color={palette.accentText} />
        </Pressable>
      ) : null}

      <UploadMenu
        visible={menuOpen}
        onClose={() => setMenuOpen(false)}
        onSelect={handleSelect}
      />
    </View>
  );
}
