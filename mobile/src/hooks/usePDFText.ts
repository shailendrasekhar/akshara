/**
 * PDF text extraction using pdfjs-dist.
 * Extracts text per page for TTS use.
 */
import { useState, useCallback } from 'react';
import * as FileSystem from 'expo-file-system';

// Lazy import pdfjs to avoid issues at module load time
let pdfjsLib: any = null;

async function getPdfjs() {
  if (!pdfjsLib) {
    pdfjsLib = require('pdfjs-dist/legacy/build/pdf');
    // Disable worker — React Native doesn't support workers
    pdfjsLib.GlobalWorkerOptions.workerSrc = '';
  }
  return pdfjsLib;
}

export function usePDFText() {
  const [pageTexts, setPageTexts] = useState<string[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const [pageCount, setPageCount] = useState(0);

  const extractAllPages = useCallback(async (fileUri: string): Promise<string[]> => {
    setIsExtracting(true);
    setPageTexts([]);

    try {
      const pdfjs = await getPdfjs();

      // Read file as base64
      const base64 = await FileSystem.readAsStringAsync(fileUri, {
        encoding: FileSystem.EncodingType.Base64,
      });

      // Convert base64 to Uint8Array
      const binaryString = atob(base64);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      const loadingTask = pdfjs.getDocument({ data: bytes });
      const pdf = await loadingTask.promise;
      const numPages = pdf.numPages;
      setPageCount(numPages);

      const texts: string[] = [];
      for (let p = 1; p <= numPages; p++) {
        try {
          const page = await pdf.getPage(p);
          const content = await page.getTextContent();
          const pageText = content.items
            .map((item: any) => item.str)
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();
          texts.push(pageText);
        } catch {
          texts.push('');
        }
      }

      setPageTexts(texts);
      setIsExtracting(false);
      return texts;
    } catch (err) {
      console.warn('PDF text extraction failed:', err);
      setIsExtracting(false);
      return [];
    }
  }, []);

  const getPageText = useCallback(
    (pageIndex: number): string => {
      return pageTexts[pageIndex] ?? '';
    },
    [pageTexts]
  );

  return { pageTexts, pageCount, isExtracting, extractAllPages, getPageText };
}
