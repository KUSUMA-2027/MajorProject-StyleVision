import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import Constants from 'expo-constants';
import { Colors, Spacing, BorderRadius, Typography, Shadows } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

function resolveApiUrl(): string {
  const envUrl = process.env.EXPO_PUBLIC_API_URL;
  if (envUrl && !envUrl.includes('localhost') && !envUrl.includes('127.0.0.1')) {
    return envUrl;
  }
  const hostUri = Constants.expoConfig?.hostUri;
  if (hostUri) {
    const hostIp = hostUri.split(':')[0];
    if (hostIp) {
      return `http://${hostIp}:8000`;
    }
  }
  return envUrl || 'http://10.92.114.240:8000';
}

const API_URL = resolveApiUrl();

export default function HomeDashboard() {
  const router = useRouter();
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [backendDetails, setBackendDetails] = useState<string>('');
  const [refreshing, setRefreshing] = useState(false);

  const checkHealth = async () => {
    try {
      setBackendStatus('checking');
      const res = await fetch(`${API_URL}/health`, { method: 'GET' });
      if (res.ok) {
        const data = await res.json();
        setBackendStatus('connected');
        setBackendDetails(`${data.app} v${data.version} (${data.tryon_mode} mode)`);
      } else {
        setBackendStatus('disconnected');
        setBackendDetails(`HTTP ${res.status}`);
      }
    } catch {
      setBackendStatus('disconnected');
      setBackendDetails('Unreachable');
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await checkHealth();
    setRefreshing(false);
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.primary}
          />
        }
      >
        {/* Top Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.brandTitle}>StyleVision</Text>
            <Text style={styles.brandSubtitle}>Personalized Virtual Styling</Text>
          </View>
          <TouchableOpacity
            style={styles.avatarButton}
            onPress={() => router.push('/(tabs)/profile')}
            accessibilityLabel="Open Profile"
          >
            <Text style={styles.avatarText}>👤</Text>
          </TouchableOpacity>
        </View>

        {/* Backend Connection Status Pill */}
        <Card style={styles.statusCard} variant="flat">
          <View style={styles.statusRow}>
            <View style={styles.statusIndicator}>
              <View
                style={[
                  styles.statusDot,
                  backendStatus === 'connected' && styles.statusConnected,
                  backendStatus === 'disconnected' && styles.statusDisconnected,
                  backendStatus === 'checking' && styles.statusChecking,
                ]}
              />
              <Text style={styles.statusText}>
                {backendStatus === 'connected'
                  ? `Backend Active: ${backendDetails}`
                  : backendStatus === 'checking'
                  ? 'Connecting to backend...'
                  : `Backend offline (${API_URL})`}
              </Text>
            </View>
            <TouchableOpacity onPress={checkHealth}>
              <Text style={styles.refreshText}>↻</Text>
            </TouchableOpacity>
          </View>
        </Card>

        {/* Hero Banner */}
        <Card style={styles.heroCard} variant="elevated">
          <Badge label="AI FASHION TECH" variant="primary" style={styles.heroBadge} />
          <Text style={styles.heroHeading}>Try on Any Look Virtually</Text>
          <Text style={styles.heroBody}>
            Upload your photo once. Explore clothing, jewelry, makeup, and hairstyles
            powered by computer vision.
          </Text>
          <Button
            title="Start Virtual Styling"
            variant="primary"
            size="md"
            onPress={() => router.push('/(tabs)/try-on')}
            style={styles.heroButton}
          />
        </Card>

        {/* Category Shortcuts Section */}
        <Text style={styles.sectionHeading}>Styling Studios</Text>
        <View style={styles.categoriesGrid}>
          {/* Outfits */}
          <Card
            style={styles.categoryCard}
            onPress={() => router.push('/try-on/outfit')}
          >
            <View style={styles.categoryIconWrap}>
              <Text style={styles.categoryIcon}>👗</Text>
            </View>
            <Text style={styles.categoryTitle}>Outfits</Text>
            <Text style={styles.categoryDesc}>CatVTON clothing try-on</Text>
            <Badge label="Diffusion" variant="primary" style={styles.categoryBadge} />
          </Card>

          {/* Accessories */}
          <Card
            style={styles.categoryCard}
            onPress={() => router.push('/try-on/accessories')}
          >
            <View style={styles.categoryIconWrap}>
              <Text style={styles.categoryIcon}>💍</Text>
            </View>
            <Text style={styles.categoryTitle}>Accessories</Text>
            <Text style={styles.categoryDesc}>Jewelry, glasses & bags</Text>
            <Badge label="Landmarks" variant="success" style={styles.categoryBadge} />
          </Card>

          {/* Makeup */}
          <Card
            style={styles.categoryCard}
            onPress={() => router.push('/try-on/makeup')}
          >
            <View style={styles.categoryIconWrap}>
              <Text style={styles.categoryIcon}>💄</Text>
            </View>
            <Text style={styles.categoryTitle}>Makeup</Text>
            <Text style={styles.categoryDesc}>Lipstick, eyeshadow & blush</Text>
            <Badge label="Facial Blend" variant="warning" style={styles.categoryBadge} />
          </Card>

          {/* Hairstyles */}
          <Card
            style={styles.categoryCard}
            onPress={() => router.push('/try-on/hairstyle')}
          >
            <View style={styles.categoryIconWrap}>
              <Text style={styles.categoryIcon}>💇‍♀️</Text>
            </View>
            <Text style={styles.categoryTitle}>Hairstyles</Text>
            <Text style={styles.categoryDesc}>Cuts, colors & lengths</Text>
            <Badge label="Head Pose" variant="muted" style={styles.categoryBadge} />
          </Card>
        </View>

        {/* How It Works Guide */}
        <Text style={styles.sectionHeading}>How It Works</Text>
        <Card style={styles.stepsCard} variant="outlined">
          <View style={styles.stepItem}>
            <View style={styles.stepNumber}><Text style={styles.stepNumText}>1</Text></View>
            <View style={styles.stepInfo}>
              <Text style={styles.stepTitle}>Upload a Portrait</Text>
              <Text style={styles.stepDesc}>Front-facing photo with clear lighting and neutral pose.</Text>
            </View>
          </View>
          <View style={styles.stepDivider} />
          <View style={styles.stepItem}>
            <View style={styles.stepNumber}><Text style={styles.stepNumText}>2</Text></View>
            <View style={styles.stepInfo}>
              <Text style={styles.stepTitle}>Choose a Style</Text>
              <Text style={styles.stepDesc}>Browse garments, jewelry, makeup shades, or haircuts.</Text>
            </View>
          </View>
          <View style={styles.stepDivider} />
          <View style={styles.stepItem}>
            <View style={styles.stepNumber}><Text style={styles.stepNumText}>3</Text></View>
            <View style={styles.stepInfo}>
              <Text style={styles.stepTitle}>Instant Try-On</Text>
              <Text style={styles.stepDesc}>Compare before-and-after results and save to your wardrobe.</Text>
            </View>
          </View>
        </Card>

        {/* Admin Portal Shortcut */}
        <Card
          style={styles.adminCard}
          variant="flat"
          onPress={() => router.push('/admin/catalogue')}
        >
          <View style={styles.adminRow}>
            <View>
              <Text style={styles.adminTitle}>Admin Catalogue Management</Text>
              <Text style={styles.adminSubtitle}>Manage outfits, accessories & styles</Text>
            </View>
            <Text style={styles.adminArrow}>→</Text>
          </View>
        </Card>

        {/* Footer */}
        <Text style={styles.footerText}>
          StyleVision · Final Year MCA Capstone Project
        </Text>
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.lg,
  },
  brandTitle: {
    fontSize: Typography.sizes.xxl,
    fontWeight: Typography.weights.heavy,
    color: Colors.textPrimary,
    letterSpacing: 0.5,
  },
  brandSubtitle: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginTop: 2,
  },
  avatarButton: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  avatarText: {
    fontSize: 20,
  },
  statusCard: {
    padding: Spacing.sm + 2,
    marginBottom: Spacing.lg,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  statusIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: Spacing.sm,
  },
  statusConnected: {
    backgroundColor: Colors.success,
  },
  statusDisconnected: {
    backgroundColor: Colors.error,
  },
  statusChecking: {
    backgroundColor: Colors.warning,
  },
  statusText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    flex: 1,
  },
  refreshText: {
    fontSize: 16,
    color: Colors.primaryLight,
    paddingHorizontal: Spacing.sm,
  },
  heroCard: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.xxl,
    marginBottom: Spacing.xxl,
    borderWidth: 1,
    borderColor: Colors.borderLight,
    ...Shadows.glow,
  },
  heroBadge: {
    marginBottom: Spacing.md,
  },
  heroHeading: {
    fontSize: Typography.sizes.xl,
    fontWeight: Typography.weights.heavy,
    color: Colors.textPrimary,
    marginBottom: Spacing.sm,
  },
  heroBody: {
    fontSize: Typography.sizes.sm,
    color: Colors.textSecondary,
    lineHeight: 20,
    marginBottom: Spacing.lg,
  },
  heroButton: {
    alignSelf: 'stretch',
  },
  sectionHeading: {
    fontSize: Typography.sizes.lg,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: Spacing.md,
  },
  categoriesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: Spacing.xxl,
  },
  categoryCard: {
    width: '48%',
    marginBottom: Spacing.md,
    padding: Spacing.md,
    backgroundColor: Colors.surfaceCard,
  },
  categoryIconWrap: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.primaryGlow,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm,
  },
  categoryIcon: {
    fontSize: 22,
  },
  categoryTitle: {
    fontSize: Typography.sizes.md,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 2,
  },
  categoryDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginBottom: Spacing.sm,
  },
  categoryBadge: {
    alignSelf: 'flex-start',
  },
  stepsCard: {
    padding: Spacing.lg,
    backgroundColor: Colors.surface,
    marginBottom: Spacing.xxl,
  },
  stepItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  stepNumber: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.md,
  },
  stepNumText: {
    color: Colors.textPrimary,
    fontWeight: Typography.weights.bold,
    fontSize: Typography.sizes.sm,
  },
  stepInfo: {
    flex: 1,
  },
  stepTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 2,
  },
  stepDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
  },
  stepDivider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.md,
    marginLeft: 40,
  },
  adminCard: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.lg,
    marginBottom: Spacing.xl,
  },
  adminRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  adminTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight,
  },
  adminSubtitle: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: 2,
  },
  adminArrow: {
    fontSize: 18,
    color: Colors.primaryLight,
  },
  footerText: {
    textAlign: 'center',
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: Spacing.md,
  },
});
