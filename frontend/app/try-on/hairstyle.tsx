import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { api } from '@/services/api';

interface StyleItem {
  item_id: string;
  name: string;
  category: string;
  subcategory?: string;
  description?: string;
  color?: string;
  tags: string[];
}

interface HairColor {
  id: string;
  name: string;
  hex: string;
}

const HAIR_EMOJIS: Record<string, string> = {
  short: '💇‍♂️',
  medium: '👩‍🦱',
  long: '👱‍♀️',
  updo: '💇‍♀️',
};

export default function HairstyleScreen() {
  const router = useRouter();
  const [items, setItems] = useState<StyleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedColor, setSelectedColor] = useState<string>('c-1');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  const colors: HairColor[] = [
    { id: 'c-1', name: 'Jet Black', hex: '#1C1C1E' },
    { id: 'c-2', name: 'Mocha Brown', hex: '#4E342E' },
    { id: 'c-3', name: 'Honey Blonde', hex: '#D4AF37' },
    { id: 'c-4', name: 'Burgundy Wine', hex: '#581845' },
    { id: 'c-5', name: 'Platinum Ice', hex: '#B0BEC5' },
  ];

  const loadCatalogue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.catalogue.list('hairstyle');
      setItems(data.items ?? []);
      if (data.items?.length > 0) setSelectedId(data.items[0].item_id);
    } catch (err: any) {
      setError(err.message || 'Could not load hairstyle catalogue.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCatalogue();
  }, [loadCatalogue]);

  const handleApply = async () => {
    if (!selectedId) {
      Alert.alert('Select Hairstyle', 'Please choose a hairstyle from the catalogue.');
      return;
    }
    const chosenStyle = items.find((h) => h.item_id === selectedId);
    const chosenColor = colors.find((c) => c.id === selectedColor);
    setIsProcessing(true);
    try {
      await api.tryon.hairstyle('img-demo-person', selectedId, chosenColor?.hex);
      router.push({
        pathname: '/result',
        params: {
          category: 'hairstyle',
          title: chosenStyle?.name ?? 'Hairstyle Look',
          style: `${chosenColor?.name ?? 'Natural Color'} • Head Alignment`,
          itemId: selectedId,
        },
      });
    } catch (err: any) {
      Alert.alert('Try-On Error', err.message || 'Could not process hairstyle fitting.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Engine Banner */}
        <Card style={styles.engineCard} variant="flat">
          <View style={styles.engineRow}>
            <Text style={styles.engineIcon}>✂️</Text>
            <View style={styles.engineInfo}>
              <Text style={styles.engineTitle}>Head Mesh & Forehead Landmark Anchor</Text>
              <Text style={styles.engineDesc}>
                Perspective scaling matching yaw/pitch head orientation (Prototype mode)
              </Text>
            </View>
            <Badge label="Landmark Anchor" variant="muted" />
          </View>
        </Card>

        {/* Photo prompt */}
        <Text style={styles.sectionHeading}>1. Your Portrait</Text>
        <TouchableOpacity style={styles.photoCard} onPress={() => router.push('/upload')}>
          <Text style={styles.photoIcon}>📷</Text>
          <View style={styles.photoTextWrap}>
            <Text style={styles.photoTitle}>Tap to upload your portrait</Text>
            <Text style={styles.photoDesc}>Hairline and forehead visible without hats or obstructions.</Text>
          </View>
          <Text style={styles.photoChevron}>→</Text>
        </TouchableOpacity>

        {/* Hairstyle Selection Grid */}
        <Text style={styles.sectionHeading}>2. Select Hairstyle</Text>

        {loading && (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="large" color={Colors.primary} />
            <Text style={styles.loadingText}>Loading hairstyles...</Text>
          </View>
        )}

        {!loading && error && (
          <ErrorMessage message={error} onRetry={loadCatalogue} />
        )}

        {!loading && !error && items.length === 0 && (
          <View style={styles.emptyWrap}>
            <Text style={styles.emptyIcon}>💇‍♀️</Text>
            <Text style={styles.emptyText}>No hairstyles in catalogue yet.</Text>
          </View>
        )}

        {!loading && !error && items.length > 0 && (
          <View style={styles.stylesGrid}>
            {items.map((hair) => {
              const isSelected = selectedId === hair.item_id;
              const emoji = HAIR_EMOJIS[hair.subcategory ?? 'medium'] ?? '💇‍♀️';
              return (
                <TouchableOpacity
                  key={hair.item_id}
                  activeOpacity={0.8}
                  onPress={() => setSelectedId(hair.item_id)}
                  style={[
                    styles.hairCard,
                    isSelected && styles.hairCardSelected,
                  ]}
                >
                  <View style={styles.hairEmojiWrap}>
                    <Text style={styles.hairEmoji}>{emoji}</Text>
                  </View>
                  <Text style={styles.hairName} numberOfLines={2}>
                    {hair.name}
                  </Text>
                  {hair.subcategory && (
                    <Badge
                      label={hair.subcategory.toUpperCase()}
                      variant={isSelected ? 'primary' : 'muted'}
                    />
                  )}
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        {/* Hair Color Selection */}
        <Text style={styles.sectionHeading}>3. Select Color Tint</Text>
        <View style={styles.colorRow}>
          {colors.map((color) => {
            const isSelected = selectedColor === color.id;
            return (
              <TouchableOpacity
                key={color.id}
                onPress={() => setSelectedColor(color.id)}
                style={[
                  styles.colorOption,
                  isSelected && styles.colorOptionSelected,
                ]}
              >
                <View style={[styles.colorDot, { backgroundColor: color.hex }]} />
                <Text style={[styles.colorLabel, isSelected && styles.colorLabelSelected]}>
                  {color.name}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Action Button */}
        <Button
          title={isProcessing ? 'Aligning Hairstyle Mesh...' : 'Explore Hairstyle Look 💇'}
          variant="primary"
          size="lg"
          loading={isProcessing}
          disabled={!selectedId || loading}
          onPress={handleApply}
          style={styles.actionBtn}
        />
      </ScrollView>
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
  content: {
    padding: Spacing.xl,
    paddingBottom: Spacing.xxxl * 2,
  },
  engineCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    marginBottom: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  engineRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  engineIcon: {
    fontSize: 24,
    marginRight: Spacing.md,
  },
  engineInfo: {
    flex: 1,
  },
  engineTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
  },
  engineDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: 2,
  },
  photoCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surfaceCard,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.primaryGlow,
    borderStyle: 'dashed',
    padding: Spacing.md,
    marginBottom: Spacing.xl,
  },
  photoIcon: { fontSize: 28, marginRight: Spacing.md },
  photoTextWrap: { flex: 1 },
  photoTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight,
  },
  photoDesc: { fontSize: Typography.sizes.xs, color: Colors.textMuted, marginTop: 2 },
  photoChevron: { fontSize: 20, color: Colors.primaryLight },
  sectionHeading: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textSecondary,
    marginBottom: Spacing.sm,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  loadingWrap: { alignItems: 'center', paddingVertical: Spacing.xxl },
  loadingText: { color: Colors.textMuted, fontSize: Typography.sizes.xs, marginTop: Spacing.sm },
  emptyWrap: { alignItems: 'center', paddingVertical: Spacing.xxl },
  emptyIcon: { fontSize: 40, marginBottom: Spacing.sm },
  emptyText: { color: Colors.textMuted, fontSize: Typography.sizes.sm },
  stylesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: Spacing.xxl,
  },
  hairCard: {
    width: '48%',
    backgroundColor: Colors.surfaceCard,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    borderWidth: 1.5,
    borderColor: Colors.border,
    alignItems: 'center',
  },
  hairCardSelected: {
    borderColor: Colors.primary,
    backgroundColor: Colors.surfaceHover,
  },
  hairEmojiWrap: {
    width: 60,
    height: 60,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm,
  },
  hairEmoji: {
    fontSize: 32,
  },
  hairName: {
    fontSize: Typography.sizes.xs,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 4,
    textAlign: 'center',
  },
  colorRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    marginBottom: Spacing.xxl,
  },
  colorOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  colorOptionSelected: {
    borderColor: Colors.primary,
    backgroundColor: Colors.surfaceHover,
  },
  colorDot: {
    width: 14,
    height: 14,
    borderRadius: 7,
    marginRight: Spacing.sm,
    borderWidth: 1,
    borderColor: '#FFFFFF44',
  },
  colorLabel: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
  },
  colorLabelSelected: {
    color: Colors.textPrimary,
    fontWeight: Typography.weights.bold,
  },
  actionBtn: {
    marginTop: Spacing.sm,
  },
});
