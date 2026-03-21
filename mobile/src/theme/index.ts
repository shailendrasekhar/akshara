import { useColorScheme } from 'react-native';

export const lightColors = {
  background: '#ffffff',
  surface: '#f5f5f5',
  border: '#e0e0e0',
  text: '#000000',
  textSecondary: '#555555',
  accent: '#000000',
  accentText: '#ffffff',
  ttsActive: 'rgba(250, 204, 21, 0.4)',
  searchResult: 'rgba(34, 197, 94, 0.35)',
  searchActive: 'rgba(249, 115, 22, 0.5)',
  danger: '#ef4444',
  toolbar: '#ffffff',
  toolbarBorder: '#e0e0e0',
};

export const darkColors = {
  background: '#000000',
  surface: '#111111',
  border: '#2a2a2a',
  text: '#ffffff',
  textSecondary: '#a0a0a0',
  accent: '#ffffff',
  accentText: '#000000',
  ttsActive: 'rgba(250, 204, 21, 0.35)',
  searchResult: 'rgba(34, 197, 94, 0.35)',
  searchActive: 'rgba(249, 115, 22, 0.5)',
  danger: '#f87171',
  toolbar: '#0a0a0a',
  toolbarBorder: '#2a2a2a',
};

export type Colors = typeof lightColors;

export function useTheme(): { colors: Colors; isDark: boolean } {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  return { colors: isDark ? darkColors : lightColors, isDark };
}

export const typography = {
  fontSizeXS: 11,
  fontSizeSM: 13,
  fontSizeMD: 15,
  fontSizeLG: 18,
  fontSizeXL: 24,
  fontSizeXXL: 36,
  letterSpacingWide: 2,
  letterSpacingXWide: 6,
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
};
