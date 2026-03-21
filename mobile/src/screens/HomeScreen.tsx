import React, { useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  SafeAreaView,
  Alert,
} from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useTheme } from '../theme';
import { useRecentFiles, RecentFile } from '../hooks/useRecentFiles';
import { RootStackParamList } from '../../App';

type Props = {
  navigation: NativeStackNavigationProp<RootStackParamList, 'Home'>;
};

export function HomeScreen({ navigation }: Props) {
  const { colors, isDark } = useTheme();
  const { recentFiles, addRecentFile, clearRecentFiles } = useRecentFiles();

  const openPDF = useCallback(async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
      });

      if (result.canceled || !result.assets?.[0]) return;

      const asset = result.assets[0];
      const destUri = `${FileSystem.documentDirectory}pdfs/${asset.name}`;

      // Ensure pdfs directory exists
      await FileSystem.makeDirectoryAsync(`${FileSystem.documentDirectory}pdfs/`, {
        intermediates: true,
      });

      // Copy to persistent storage
      await FileSystem.copyAsync({ from: asset.uri, to: destUri });

      await addRecentFile(destUri, asset.name);

      navigation.navigate('Reader', {
        fileUri: destUri,
        fileName: asset.name,
      });
    } catch (err) {
      Alert.alert('Error', 'Could not open the PDF file.');
    }
  }, [navigation, addRecentFile]);

  const openRecentFile = useCallback(
    async (file: RecentFile) => {
      const info = await FileSystem.getInfoAsync(file.uri);
      if (!info.exists) {
        Alert.alert('File not found', 'This file no longer exists on your device.');
        return;
      }
      navigation.navigate('Reader', {
        fileUri: file.uri,
        fileName: file.name,
      });
    },
    [navigation]
  );

  const styles = makeStyles(colors);

  const renderRecentItem = ({ item }: { item: RecentFile }) => (
    <TouchableOpacity style={styles.recentItem} onPress={() => openRecentFile(item)}>
      <Text style={styles.recentIcon}>📄</Text>
      <View style={styles.recentInfo}>
        <Text style={styles.recentName} numberOfLines={1}>
          {item.name}
        </Text>
        <Text style={styles.recentDate}>{new Date(item.openedAt).toLocaleDateString()}</Text>
      </View>
      <Text style={styles.recentChevron}>›</Text>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container}>
      {/* Hero section */}
      <View style={styles.hero}>
        <Text style={styles.heroIcon}>📖</Text>
        <Text style={styles.heroTitle}>AKSHARA</Text>
        <Text style={styles.heroSubtitle}>PDF Reader with Text-to-Speech</Text>

        <TouchableOpacity style={styles.openBtn} onPress={openPDF} activeOpacity={0.85}>
          <Text style={styles.openBtnText}>📂  Open PDF</Text>
        </TouchableOpacity>

        <Text style={styles.hint}>
          Tap to pick a PDF from your device or iCloud Drive
        </Text>
      </View>

      {/* Recent files */}
      {recentFiles.length > 0 && (
        <View style={styles.recentSection}>
          <View style={styles.recentHeader}>
            <Text style={styles.recentTitle}>Recent Files</Text>
            <TouchableOpacity onPress={() => clearRecentFiles()}>
              <Text style={styles.clearText}>Clear</Text>
            </TouchableOpacity>
          </View>
          <FlatList
            data={recentFiles}
            keyExtractor={item => item.uri}
            renderItem={renderRecentItem}
            ItemSeparatorComponent={() => <View style={styles.separator} />}
            style={styles.recentList}
          />
        </View>
      )}

      {/* Tips */}
      <View style={styles.tips}>
        <Text style={styles.tipText}>• Swipe to turn pages</Text>
        <Text style={styles.tipText}>• Tap "Read Page" to hear TTS</Text>
        <Text style={styles.tipText}>• Bookmark your favourite pages</Text>
      </View>
    </SafeAreaView>
  );
}

function makeStyles(colors: any) {
  return StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: colors.background,
    },
    hero: {
      alignItems: 'center',
      paddingTop: 48,
      paddingHorizontal: 32,
      paddingBottom: 32,
    },
    heroIcon: {
      fontSize: 64,
      marginBottom: 16,
    },
    heroTitle: {
      fontSize: 36,
      fontWeight: '200',
      letterSpacing: 8,
      color: colors.text,
      marginBottom: 8,
    },
    heroSubtitle: {
      fontSize: 13,
      letterSpacing: 1.5,
      color: colors.textSecondary,
      marginBottom: 40,
    },
    openBtn: {
      backgroundColor: colors.accent,
      paddingVertical: 16,
      paddingHorizontal: 48,
      borderRadius: 10,
      marginBottom: 12,
    },
    openBtnText: {
      color: colors.accentText,
      fontSize: 15,
      fontWeight: '600',
      letterSpacing: 1,
    },
    hint: {
      fontSize: 12,
      color: colors.textSecondary,
      textAlign: 'center',
    },
    recentSection: {
      flex: 1,
      borderTopWidth: 1,
      borderTopColor: colors.border,
      marginTop: 8,
    },
    recentHeader: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      paddingHorizontal: 20,
      paddingVertical: 12,
    },
    recentTitle: {
      fontSize: 13,
      fontWeight: '600',
      color: colors.textSecondary,
      letterSpacing: 1,
      textTransform: 'uppercase',
    },
    clearText: {
      fontSize: 13,
      color: colors.textSecondary,
    },
    recentList: {
      flex: 1,
    },
    recentItem: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: 20,
      paddingVertical: 14,
      backgroundColor: colors.background,
    },
    recentIcon: {
      fontSize: 22,
      marginRight: 12,
    },
    recentInfo: {
      flex: 1,
    },
    recentName: {
      fontSize: 15,
      color: colors.text,
      fontWeight: '500',
    },
    recentDate: {
      fontSize: 12,
      color: colors.textSecondary,
      marginTop: 2,
    },
    recentChevron: {
      fontSize: 20,
      color: colors.textSecondary,
    },
    separator: {
      height: 1,
      backgroundColor: colors.border,
      marginLeft: 54,
    },
    tips: {
      padding: 20,
      paddingBottom: 8,
      borderTopWidth: 1,
      borderTopColor: colors.border,
    },
    tipText: {
      fontSize: 12,
      color: colors.textSecondary,
      lineHeight: 22,
    },
  });
}
