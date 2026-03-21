import { useState, useEffect, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const RECENT_FILES_KEY = '@akshara_recent_files';
const MAX_RECENT = 10;

export interface RecentFile {
  uri: string;
  name: string;
  openedAt: number;
}

export function useRecentFiles() {
  const [recentFiles, setRecentFiles] = useState<RecentFile[]>([]);

  useEffect(() => {
    loadRecentFiles();
  }, []);

  const loadRecentFiles = async () => {
    try {
      const raw = await AsyncStorage.getItem(RECENT_FILES_KEY);
      if (raw) {
        setRecentFiles(JSON.parse(raw));
      }
    } catch {
      // ignore
    }
  };

  const addRecentFile = useCallback(async (uri: string, name: string) => {
    setRecentFiles(prev => {
      const filtered = prev.filter(f => f.uri !== uri);
      const updated = [{ uri, name, openedAt: Date.now() }, ...filtered].slice(0, MAX_RECENT);
      AsyncStorage.setItem(RECENT_FILES_KEY, JSON.stringify(updated)).catch(() => {});
      return updated;
    });
  }, []);

  const clearRecentFiles = useCallback(async () => {
    await AsyncStorage.removeItem(RECENT_FILES_KEY);
    setRecentFiles([]);
  }, []);

  return { recentFiles, addRecentFile, clearRecentFiles };
}
