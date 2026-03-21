import React from 'react';
import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useTheme } from '../theme';

interface BookmarkButtonProps {
  isBookmarked: boolean;
  onPress: () => void;
}

export function BookmarkButton({ isBookmarked, onPress }: BookmarkButtonProps) {
  const { colors } = useTheme();
  return (
    <TouchableOpacity onPress={onPress} style={styles.btn} hitSlop={8}>
      <Text style={{ fontSize: 20, color: isBookmarked ? '#f59e0b' : colors.textSecondary }}>
        {isBookmarked ? '🔖' : '🏷️'}
      </Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  btn: { padding: 4 },
});
