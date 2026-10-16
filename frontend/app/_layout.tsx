/**
 * StyleVision — Root Layout (Expo Router)
 *
 * This file defines the root navigation structure.
 * Expo Router reads this file automatically because it lives at app/_layout.tsx.
 */
import { useEffect } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import * as SplashScreen from 'expo-splash-screen';

// Keep the splash screen visible while fonts or assets are loading
SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  useEffect(() => {
    SplashScreen.hideAsync();
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: '#0D0818' }}>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: '#0D0818' },
          headerTintColor: '#FFFFFF',
          headerTitleStyle: { fontWeight: '700' },
          contentStyle: { backgroundColor: '#0D0818' },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="onboarding" options={{ headerShown: false }} />
        <Stack.Screen name="(auth)/login" options={{ title: 'Sign In', presentation: 'modal' }} />
        <Stack.Screen name="(auth)/register" options={{ title: 'Create Account', presentation: 'modal' }} />
        <Stack.Screen name="upload" options={{ title: 'Upload Photo' }} />
        <Stack.Screen name="try-on/outfit" options={{ title: 'Outfit Try-On' }} />
        <Stack.Screen name="try-on/accessories" options={{ title: 'Accessories' }} />
        <Stack.Screen name="try-on/makeup" options={{ title: 'Makeup Studio' }} />
        <Stack.Screen name="try-on/hairstyle" options={{ title: 'Hairstyle Lab' }} />
        <Stack.Screen name="result" options={{ title: 'Styling Result' }} />
        <Stack.Screen name="admin/catalogue" options={{ title: 'Catalogue Admin' }} />
      </Stack>
    </GestureHandlerRootView>
  );
}
