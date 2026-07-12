/**
 * Design tokens — single source of truth for the app's look.
 * Two palettes: light (Notion-warm) and dark (Gamma-deep).
 * Everything else — spacing, radii, type — is theme-agnostic.
 */

export const lightPalette = {
  // Notion-inspired warm off-white surfaces
  bg: '#F6F5F4',
  surface: '#FFFFFF',
  surfaceElevated: '#FFFFFF',
  surfacePressed: '#EBEBEA',
  border: '#E3E2E0',

  text: '#1A1A1A',
  textMuted: '#5E5C58',
  textFaint: '#9B9A97',

  // Purple accent — absent from every competitor
  accent: '#5645D4',
  accentSoft: 'rgba(86, 69, 212, 0.1)',
  accentText: '#FFFFFF',

  violet: '#7C6BF0',
  violetSoft: 'rgba(124, 107, 240, 0.14)',

  success: '#16A34A',
  successSoft: 'rgba(22, 163, 74, 0.12)',
  warning: '#D97706',
  warningSoft: 'rgba(217, 119, 6, 0.12)',
  danger: '#DC2626',
  dangerSoft: 'rgba(220, 38, 38, 0.1)',
  info: '#2563EB',
  infoSoft: 'rgba(37, 99, 235, 0.1)',

  // Pastel card tints (rotate through these per doc)
  cardTints: ['#EDE9FE', '#D1FAE5', '#DBEAFE', '#FCE7F3', '#FEF3C7', '#F0FDF4'],
} as const;

export const darkPalette = {
  // Gamma-inspired deep dark surfaces
  bg: '#0F0F14',
  surface: '#1A1A2E',
  surfaceElevated: '#1E1E30',
  surfacePressed: '#252540',
  border: '#2D2D44',

  text: '#F0F0FF',
  textMuted: '#A0A0C0',
  textFaint: '#6B6B8A',

  // Purple accent — same hue, lighter for dark bg
  accent: '#7C6BF0',
  accentSoft: 'rgba(124, 107, 240, 0.18)',
  accentText: '#FFFFFF',

  violet: '#7C6BF0',
  violetSoft: 'rgba(124, 107, 240, 0.18)',

  success: '#3FB984',
  successSoft: 'rgba(63, 185, 132, 0.16)',
  warning: '#F59E0B',
  warningSoft: 'rgba(245, 158, 11, 0.16)',
  danger: '#F26D6D',
  dangerSoft: 'rgba(242, 109, 109, 0.16)',
  info: '#5AA9F0',
  infoSoft: 'rgba(90, 169, 240, 0.16)',

  cardTints: ['#1E1A3A', '#0F2A1E', '#0F1E2E', '#2A1020', '#2A2010', '#102A10'],
} as const;

// Default palette re-export (static fallback for non-component contexts)
export const palette = lightPalette;
// Union so components can accept either palette without literal-type mismatches
export type Palette = typeof lightPalette | typeof darkPalette;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 18,
  xl: 26,
  pill: 999,
} as const;

export const typography = {
  display:    { fontSize: 32, fontWeight: '800' as const, letterSpacing: -0.5 },
  title:      { fontSize: 24, fontWeight: '700' as const, letterSpacing: -0.3 },
  heading:    { fontSize: 18, fontWeight: '700' as const },
  body:       { fontSize: 16, fontWeight: '400' as const },
  bodyStrong: { fontSize: 16, fontWeight: '600' as const },
  caption:    { fontSize: 13, fontWeight: '500' as const },
  micro:      { fontSize: 11, fontWeight: '600' as const, letterSpacing: 0.4 },
} as const;

export function makeShadow(accentColor: string) {
  return {
    card: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.08,
      shadowRadius: 8,
      elevation: 4,
    },
    floating: {
      shadowColor: accentColor,
      shadowOffset: { width: 0, height: 6 },
      shadowOpacity: 0.35,
      shadowRadius: 18,
      elevation: 12,
    },
  };
}

export const shadow = makeShadow(lightPalette.accent);
