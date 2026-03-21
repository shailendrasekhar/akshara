import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  Alert,
  ActivityIndicator,
  Modal,
  FlatList,
  TextInput,
} from 'react-native';
import Pdf from 'react-native-pdf';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RouteProp } from '@react-navigation/native';
import { useTheme } from '../theme';
import { useTTS } from '../hooks/useTTS';
import { usePDFText } from '../hooks/usePDFText';
import { TTSControls } from '../components/TTSControls';
import { RootStackParamList } from '../../App';

type Props = {
  navigation: NativeStackNavigationProp<RootStackParamList, 'Reader'>;
  route: RouteProp<RootStackParamList, 'Reader'>;
};

function bookmarkKey(fileUri: string) {
  return `@akshara_bookmarks_${fileUri}`;
}

export function ReaderScreen({ navigation, route }: Props) {
  const { fileUri, fileName } = route.params;
  const { colors } = useTheme();
  const tts = useTTS();
  const pdfText = usePDFText();

  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [bookmarks, setBookmarks] = useState<number[]>([]);
  const [showBookmarks, setShowBookmarks] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const pdfRef = useRef<any>(null);

  // Set navigation title
  useEffect(() => {
    navigation.setOptions({
      title: fileName.replace('.pdf', ''),
      headerRight: () => (
        <View style={{ flexDirection: 'row', gap: 16, marginRight: 4 }}>
          <TouchableOpacity onPress={() => setShowSearch(s => !s)} hitSlop={8}>
            <Text style={{ fontSize: 18, color: colors.text }}>🔍</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setShowBookmarks(true)} hitSlop={8}>
            <Text style={{ fontSize: 18, color: colors.text }}>🔖</Text>
          </TouchableOpacity>
        </View>
      ),
    });
  }, [navigation, fileName, colors]);

  // Load bookmarks
  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(bookmarkKey(fileUri));
        if (raw) setBookmarks(JSON.parse(raw));
      } catch {}
    })();
  }, [fileUri]);

  // Extract text for TTS when PDF loads
  const onPDFLoad = useCallback(
    async (numberOfPages: number) => {
      setTotalPages(numberOfPages);
      setLoading(false);
      pdfText.extractAllPages(fileUri);
    },
    [fileUri, pdfText]
  );

  const onPageChanged = useCallback(
    (page: number) => {
      setCurrentPage(page);
      // Stop TTS when page changes
      if (!tts.isIdle) tts.stop();
    },
    [tts]
  );

  // Read current page
  const readPage = useCallback(() => {
    const text = pdfText.getPageText(currentPage - 1);
    if (!text) {
      Alert.alert('No text', 'Could not extract text from this page. It may be image-based.');
      return;
    }
    tts.speak(text);
  }, [currentPage, pdfText, tts]);

  // Navigate to page
  const goToPage = useCallback((page: number) => {
    pdfRef.current?.setPage(page);
    setCurrentPage(page);
  }, []);

  // Bookmarks
  const toggleBookmark = useCallback(async () => {
    const updated = bookmarks.includes(currentPage)
      ? bookmarks.filter(p => p !== currentPage)
      : [...bookmarks, currentPage].sort((a, b) => a - b);
    setBookmarks(updated);
    await AsyncStorage.setItem(bookmarkKey(fileUri), JSON.stringify(updated));
  }, [bookmarks, currentPage, fileUri]);

  const isBookmarked = bookmarks.includes(currentPage);

  const styles = makeStyles(colors);

  return (
    <SafeAreaView style={styles.container}>
      {/* Top navigation bar */}
      <View style={styles.navbar}>
        <TouchableOpacity
          onPress={() => (currentPage > 1 ? goToPage(currentPage - 1) : null)}
          style={[styles.navBtn, currentPage <= 1 && styles.navBtnDisabled]}
          disabled={currentPage <= 1}
        >
          <Text style={styles.navBtnText}>◀</Text>
        </TouchableOpacity>

        <Text style={styles.pageIndicator}>
          {currentPage} / {totalPages}
        </Text>

        <TouchableOpacity
          onPress={() => (currentPage < totalPages ? goToPage(currentPage + 1) : null)}
          style={[styles.navBtn, currentPage >= totalPages && styles.navBtnDisabled]}
          disabled={currentPage >= totalPages}
        >
          <Text style={styles.navBtnText}>▶</Text>
        </TouchableOpacity>

        <TouchableOpacity onPress={toggleBookmark} style={styles.bookmarkBtn}>
          <Text style={{ fontSize: 20 }}>{isBookmarked ? '🔖' : '🏷️'}</Text>
        </TouchableOpacity>
      </View>

      {/* Search bar */}
      {showSearch && (
        <View style={styles.searchBar}>
          <TextInput
            style={styles.searchInput}
            placeholder="Find in PDF..."
            placeholderTextColor={colors.textSecondary}
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoFocus
            returnKeyType="search"
          />
          <TouchableOpacity onPress={() => { setShowSearch(false); setSearchQuery(''); }}>
            <Text style={styles.searchClose}>✕</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* PDF Viewer */}
      <View style={styles.pdfContainer}>
        {loading && (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator size="large" color={colors.text} />
            <Text style={styles.loadingText}>Opening PDF…</Text>
          </View>
        )}
        <Pdf
          ref={pdfRef}
          source={{ uri: fileUri, cache: true }}
          style={styles.pdf}
          onLoadComplete={onPDFLoad}
          onPageChanged={onPageChanged}
          onError={err => {
            console.error('PDF error:', err);
            Alert.alert('Error', 'Could not render the PDF.');
          }}
          enablePaging
          horizontal={false}
          page={currentPage}
          trustAllCerts={false}
          fitPolicy={0}
        />

        {/* TTS extraction indicator */}
        {pdfText.isExtracting && (
          <View style={styles.extractingBadge}>
            <ActivityIndicator size="small" color="#ffffff" />
            <Text style={styles.extractingText}>Extracting text…</Text>
          </View>
        )}
      </View>

      {/* TTS Controls */}
      <TTSControls
        state={tts.state}
        speed={tts.speed}
        isExtracting={pdfText.isExtracting}
        onReadPage={readPage}
        onPause={tts.pause}
        onResume={tts.resume}
        onStop={tts.stop}
        onSpeedChange={tts.setSpeed}
      />

      {/* Bookmarks Modal */}
      <Modal visible={showBookmarks} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Bookmarks</Text>
            <TouchableOpacity onPress={() => setShowBookmarks(false)}>
              <Text style={styles.modalClose}>Done</Text>
            </TouchableOpacity>
          </View>

          {bookmarks.length === 0 ? (
            <View style={styles.emptyBookmarks}>
              <Text style={styles.emptyText}>🏷️</Text>
              <Text style={styles.emptyLabel}>No bookmarks yet</Text>
              <Text style={styles.emptyHint}>Tap the bookmark icon to save a page</Text>
            </View>
          ) : (
            <FlatList
              data={bookmarks}
              keyExtractor={item => String(item)}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={styles.bookmarkItem}
                  onPress={() => {
                    goToPage(item);
                    setShowBookmarks(false);
                  }}
                >
                  <Text style={styles.bookmarkIcon}>🔖</Text>
                  <Text style={styles.bookmarkPageText}>Page {item}</Text>
                  <Text style={styles.bookmarkChevron}>›</Text>
                </TouchableOpacity>
              )}
              ItemSeparatorComponent={() => <View style={styles.separator} />}
            />
          )}

          {bookmarks.length > 0 && (
            <TouchableOpacity
              style={styles.clearBookmarksBtn}
              onPress={async () => {
                setBookmarks([]);
                await AsyncStorage.removeItem(bookmarkKey(fileUri));
              }}
            >
              <Text style={styles.clearBookmarksText}>Clear All Bookmarks</Text>
            </TouchableOpacity>
          )}
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

function makeStyles(colors: any) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    navbar: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderBottomWidth: 1,
      borderBottomColor: colors.toolbarBorder,
      backgroundColor: colors.toolbar,
    },
    navBtn: {
      padding: 8,
      borderRadius: 6,
      borderWidth: 1,
      borderColor: colors.border,
    },
    navBtnDisabled: {
      opacity: 0.3,
    },
    navBtnText: {
      fontSize: 16,
      color: colors.text,
    },
    pageIndicator: {
      flex: 1,
      textAlign: 'center',
      fontSize: 14,
      color: colors.text,
      fontWeight: '500',
    },
    bookmarkBtn: {
      padding: 8,
    },
    searchBar: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.surface,
      borderBottomWidth: 1,
      borderBottomColor: colors.border,
      paddingHorizontal: 12,
      paddingVertical: 6,
    },
    searchInput: {
      flex: 1,
      fontSize: 15,
      color: colors.text,
      paddingVertical: 6,
    },
    searchClose: {
      fontSize: 16,
      color: colors.textSecondary,
      paddingLeft: 12,
    },
    pdfContainer: {
      flex: 1,
      backgroundColor: colors.background,
    },
    pdf: {
      flex: 1,
      backgroundColor: colors.background,
    },
    loadingOverlay: {
      ...StyleSheet.absoluteFillObject,
      justifyContent: 'center',
      alignItems: 'center',
      backgroundColor: colors.background,
      zIndex: 10,
    },
    loadingText: {
      marginTop: 12,
      fontSize: 14,
      color: colors.textSecondary,
    },
    extractingBadge: {
      position: 'absolute',
      bottom: 16,
      right: 16,
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      backgroundColor: 'rgba(0,0,0,0.7)',
      borderRadius: 20,
      paddingHorizontal: 12,
      paddingVertical: 6,
    },
    extractingText: {
      fontSize: 12,
      color: '#ffffff',
    },
    modalContainer: {
      flex: 1,
      backgroundColor: colors.background,
    },
    modalHeader: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      paddingHorizontal: 20,
      paddingVertical: 16,
      borderBottomWidth: 1,
      borderBottomColor: colors.border,
    },
    modalTitle: {
      fontSize: 18,
      fontWeight: '600',
      color: colors.text,
    },
    modalClose: {
      fontSize: 16,
      color: colors.text,
      fontWeight: '500',
    },
    emptyBookmarks: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      gap: 8,
    },
    emptyText: { fontSize: 48 },
    emptyLabel: {
      fontSize: 18,
      fontWeight: '500',
      color: colors.text,
    },
    emptyHint: {
      fontSize: 13,
      color: colors.textSecondary,
    },
    bookmarkItem: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: 20,
      paddingVertical: 16,
    },
    bookmarkIcon: { fontSize: 20, marginRight: 12 },
    bookmarkPageText: {
      flex: 1,
      fontSize: 16,
      color: colors.text,
    },
    bookmarkChevron: {
      fontSize: 20,
      color: colors.textSecondary,
    },
    separator: {
      height: 1,
      backgroundColor: colors.border,
      marginLeft: 52,
    },
    clearBookmarksBtn: {
      margin: 20,
      padding: 14,
      borderRadius: 10,
      borderWidth: 1,
      borderColor: colors.danger,
      alignItems: 'center',
    },
    clearBookmarksText: {
      color: colors.danger,
      fontSize: 15,
      fontWeight: '500',
    },
  });
}
