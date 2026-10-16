/**
 * StyleVision — Design System & Theme
 * Premium fashion-tech aesthetic with deep neutral backgrounds
 * and refined purple/violet accents (#7C4DFF).
 */

export const Colors = {
  // Brand accents
  primary: '#7C4DFF',
  primaryLight: '#B388FF',
  primaryDark: '#5E35B1',
  primaryGlow: 'rgba(124, 77, 255, 0.25)',
  accentPink: '#FF4081',
  accentGold: '#FFD700',

  // Background hierarchy (dark fashion-tech theme)
  background: '#0D0818',
  backgroundSecondary: '#150E28',
  surface: '#1E1538',
  surfaceHover: '#2A1F4C',
  surfaceCard: '#1A1230',

  // Text colors
  textPrimary: '#FFFFFF',
  textSecondary: '#C5BCE0',
  textMuted: '#8476A8',
  textInverse: '#0D0818',

  // Borders & Dividers
  border: '#2C1F4D',
  borderLight: '#3D2D68',
  borderFocus: '#7C4DFF',

  // Semantic
  success: '#00E676',
  successBg: 'rgba(0, 230, 118, 0.12)',
  warning: '#FFAB00',
  warningBg: 'rgba(255, 171, 0, 0.12)',
  error: '#FF5252',
  errorBg: 'rgba(255, 82, 82, 0.12)',
  info: '#40C4FF',
  infoBg: 'rgba(64, 196, 255, 0.12)',

  // Overlays
  overlay: 'rgba(13, 8, 24, 0.75)',
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
};

export const BorderRadius = {
  sm: 6,
  md: 10,
  lg: 16,
  xl: 24,
  full: 9999,
};

export const Typography = {
  sizes: {
    xs: 11,
    sm: 13,
    md: 15,
    lg: 17,
    xl: 20,
    xxl: 26,
    hero: 34,
  },
  weights: {
    regular: '400' as const,
    medium: '500' as const,
    semibold: '600' as const,
    bold: '700' as const,
    heavy: '800' as const,
  },
};

export const Shadows = {
  card: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
    elevation: 6,
  },
  glow: {
    shadowColor: '#7C4DFF',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.45,
    shadowRadius: 12,
    elevation: 10,
  },
};
