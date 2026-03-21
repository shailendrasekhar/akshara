import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import Slider from '@react-native-community/slider';
import { useTheme } from '../theme';
import { TTSState } from '../hooks/useTTS';

interface TTSControlsProps {
  state: TTSState;
  speed: number;
  isExtracting: boolean;
  onReadPage: () => void;
  onReadSelection?: () => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  onSpeedChange: (speed: number) => void;
}

export function TTSControls({
  state,
  speed,
  isExtracting,
  onReadPage,
  onPause,
  onResume,
  onStop,
  onSpeedChange,
}: TTSControlsProps) {
  const { colors } = useTheme();

  const styles = makeStyles(colors);

  return (
    <View style={styles.container}>
      {/* Main controls row */}
      <View style={styles.row}>
        {state === 'idle' ? (
          <TouchableOpacity
            style={[styles.btn, styles.primaryBtn]}
            onPress={onReadPage}
            disabled={isExtracting}
          >
            {isExtracting ? (
              <ActivityIndicator color={colors.accentText} size="small" />
            ) : (
              <Text style={[styles.btnText, styles.primaryBtnText]}>▶  Read Page</Text>
            )}
          </TouchableOpacity>
        ) : state === 'speaking' ? (
          <>
            <TouchableOpacity style={[styles.btn, styles.secondaryBtn]} onPress={onPause}>
              <Text style={styles.btnText}>⏸  Pause</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.btn, styles.dangerBtn]} onPress={onStop}>
              <Text style={[styles.btnText, { color: colors.danger }]}>⏹  Stop</Text>
            </TouchableOpacity>
          </>
        ) : (
          <>
            <TouchableOpacity style={[styles.btn, styles.primaryBtn]} onPress={onResume}>
              <Text style={[styles.btnText, styles.primaryBtnText]}>▶  Resume</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.btn, styles.secondaryBtn]} onPress={onStop}>
              <Text style={styles.btnText}>⏹  Stop</Text>
            </TouchableOpacity>
          </>
        )}
      </View>

      {/* Speed row */}
      <View style={styles.speedRow}>
        <Text style={styles.speedLabel}>Speed: {speed.toFixed(1)}×</Text>
        <Slider
          style={styles.slider}
          minimumValue={0.5}
          maximumValue={2.0}
          step={0.1}
          value={speed}
          onValueChange={onSpeedChange}
          minimumTrackTintColor={colors.accent}
          maximumTrackTintColor={colors.border}
          thumbTintColor={colors.accent}
        />
      </View>
    </View>
  );
}

function makeStyles(colors: any) {
  return StyleSheet.create({
    container: {
      backgroundColor: colors.toolbar,
      borderTopWidth: 1,
      borderTopColor: colors.toolbarBorder,
      paddingHorizontal: 16,
      paddingVertical: 10,
    },
    row: {
      flexDirection: 'row',
      gap: 10,
      marginBottom: 8,
    },
    btn: {
      flex: 1,
      paddingVertical: 10,
      borderRadius: 8,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: 1,
      borderColor: colors.border,
    },
    primaryBtn: {
      backgroundColor: colors.accent,
      borderColor: colors.accent,
    },
    secondaryBtn: {
      backgroundColor: 'transparent',
    },
    dangerBtn: {
      backgroundColor: 'transparent',
      borderColor: colors.danger,
    },
    btnText: {
      fontSize: 14,
      fontWeight: '600',
      color: colors.text,
    },
    primaryBtnText: {
      color: colors.accentText,
    },
    speedRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
    },
    speedLabel: {
      fontSize: 12,
      color: colors.textSecondary,
      width: 80,
    },
    slider: {
      flex: 1,
      height: 28,
    },
  });
}
