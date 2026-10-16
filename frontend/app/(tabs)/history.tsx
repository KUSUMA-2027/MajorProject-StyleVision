import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { Button } from '@/components/ui/Button';

interface HistoryItem {
  id: string;
  title: string;
  category: 'outfit' | 'accessories' | 'makeup' | 'hairstyle';
  categoryLabel: string;
  createdAt: string;
  styleName: string;
}

export default function HistoryScreen() {
  const router = useRouter();
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'outfit' | 'accessories' | 'makeup' | 'hairstyle'>('all');

  // Sample items demonstrate layout and structure
  const [items, setItems] = useState<HistoryItem[]>([
    {
      id: 'look-1',
      title: 'Formal Navy Blazer Look',
      category: 'outfit',
      categoryLabel: 'Outfit Try-On',
      createdAt: 'Today, 2:30 PM',
      styleName: 'Slim Fit Midnight Blazer',
    },
    {
      id: 'look-2',
      title: 'Aviator Sunglasses & Gold Earrings',
      category: 'accessories',
      categoryLabel: 'Accessories',
      createdAt: 'Yesterday, 6:15 PM',
      styleName: 'Classic Metal Aviator',
    },
    {
      id: 'look-3',
      title: 'Berry Satin Lipstick',
      category: 'makeup',
      categoryLabel: 'Makeup',
      createdAt: 'Oct 10, 2026',
      styleName: 'Deep Crimson Shade #08',
    },
  ]);

  const handleDelete = (id: string, title: string) => {
    Alert.alert('Remove Look', `Are you sure you want to remove "${title}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          setItems((prev) => prev.filter((item) => item.id !== id));
        },
      },
    ]);
  };

  const filteredItems =
    selectedFilter === 'all'
      ? items
      : items.filter((item) => item.category === selectedFilter);

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Saved Looks</Text>
          <Text style={styles.subtitle}>
            {items.length} saved styling {items.length === 1 ? 'result' : 'results'}
          </Text>
        </View>

        {/* Filter Pills */}
        <View style={styles.filterContainer}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.filterRow}
          >
            {(
              [
                { key: 'all', label: 'All' },
                { key: 'outfit', label: 'Outfits' },
                { key: 'accessories', label: 'Accessories' },
                { key: 'makeup', label: 'Makeup' },
                { key: 'hairstyle', label: 'Hairstyles' },
              ] as const
            ).map((f) => {
              const active = selectedFilter === f.key;
              return (
                <TouchableOpacity
                  key={f.key}
                  onPress={() => setSelectedFilter(f.key)}
                  style={[styles.filterPill, active && styles.filterPillActive]}
                >
                  <Text
                    style={[styles.filterText, active && styles.filterTextActive]}
                  >
                    {f.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>

        {/* Content list or Empty State */}
        {filteredItems.length === 0 ? (
          <EmptyState
            icon="💜"
            title="No Saved Looks Yet"
            description="Experiment with virtual try-ons and save your favorite results to build your personalized style lookbook."
            actionTitle="Explore Try-On"
            onAction={() => router.push('/(tabs)/try-on')}
          />
        ) : (
          <ScrollView
            contentContainerStyle={styles.listContent}
            showsVerticalScrollIndicator={false}
          >
            {filteredItems.map((item) => (
              <Card key={item.id} style={styles.card} variant="elevated">
                <View style={styles.cardHeader}>
                  <Badge
                    label={item.categoryLabel}
                    variant={
                      item.category === 'outfit'
                        ? 'primary'
                        : item.category === 'accessories'
                        ? 'success'
                        : item.category === 'makeup'
                        ? 'warning'
                        : 'muted'
                    }
                  />
                  <Text style={styles.timeText}>{item.createdAt}</Text>
                </View>

                {/* Preview placeholders */}
                <View style={styles.previewRow}>
                  <View style={styles.previewBox}>
                    <Text style={styles.previewLabel}>ORIGINAL</Text>
                    <Text style={styles.previewIcon}>👤</Text>
                  </View>
                  <Text style={styles.previewArrow}>⇄</Text>
                  <View style={[styles.previewBox, styles.previewBoxResult]}>
                    <Text style={styles.previewLabel}>STYLED</Text>
                    <Text style={styles.previewIcon}>✨</Text>
                  </View>
                </View>

                <Text style={styles.cardTitle}>{item.title}</Text>
                <Text style={styles.cardStyleName}>Item: {item.styleName}</Text>

                <View style={styles.cardActions}>
                  <Button
                    title="Compare Before & After"
                    variant="secondary"
                    size="sm"
                    onPress={() =>
                      router.push({
                        pathname: '/result',
                        params: { title: item.title, style: item.styleName },
                      })
                    }
                    style={styles.actionButton}
                  />
                  <TouchableOpacity
                    onPress={() => handleDelete(item.id, item.title)}
                    style={styles.deleteButton}
                    accessibilityLabel="Delete Look"
                  >
                    <Text style={styles.deleteIcon}>🗑️</Text>
                  </TouchableOpacity>
                </View>
              </Card>
            ))}
          </ScrollView>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  title: {
    fontSize: Typography.sizes.xxl,
    fontWeight: Typography.weights.heavy,
    color: Colors.textPrimary,
  },
  subtitle: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: 2,
  },
  filterContainer: {
    paddingVertical: Spacing.sm,
  },
  filterRow: {
    paddingHorizontal: Spacing.xl,
  },
  filterPill: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    marginRight: Spacing.sm,
  },
  filterPillActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  filterText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium,
  },
  filterTextActive: {
    color: Colors.textPrimary,
    fontWeight: Typography.weights.bold,
  },
  listContent: {
    padding: Spacing.xl,
    paddingBottom: Spacing.xxxl * 2,
  },
  card: {
    marginBottom: Spacing.lg,
    backgroundColor: Colors.surfaceCard,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  timeText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
  },
  previewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: Spacing.sm,
    gap: Spacing.md,
  },
  previewBox: {
    flex: 1,
    height: 100,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  previewBoxResult: {
    borderColor: Colors.primary,
    backgroundColor: Colors.surfaceHover,
  },
  previewLabel: {
    fontSize: 9,
    color: Colors.textMuted,
    letterSpacing: 1,
    fontWeight: Typography.weights.bold,
    marginBottom: 4,
  },
  previewIcon: {
    fontSize: 28,
  },
  previewArrow: {
    fontSize: 18,
    color: Colors.primaryLight,
  },
  cardTitle: {
    fontSize: Typography.sizes.md,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginTop: Spacing.sm,
  },
  cardStyleName: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    marginBottom: Spacing.md,
    marginTop: 2,
  },
  cardActions: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  actionButton: {
    flex: 1,
    marginRight: Spacing.md,
  },
  deleteButton: {
    padding: Spacing.sm,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  deleteIcon: {
    fontSize: 16,
  },
});
