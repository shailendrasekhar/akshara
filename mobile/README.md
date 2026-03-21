# Akshara Mobile — iOS App

PDF Reader with Text-to-Speech for iOS, built with React Native + Expo.

## Prerequisites

- Node.js 18+
- [Expo CLI](https://docs.expo.dev/get-started/installation/): `npm install -g expo-cli eas-cli`
- Xcode 15+ (for iOS builds)
- An Apple Developer account (for device builds)

## Quick Start

```bash
cd mobile
npm install
```

### Run on iOS Simulator (requires Mac + Xcode)

```bash
npx expo run:ios
```

### Build for a real device with EAS

```bash
# Login to Expo account
eas login

# Configure your project
eas build:configure

# Build for iOS simulator (free, no Apple account needed)
eas build -p ios --profile simulator

# Build for real device (needs Apple Developer account)
eas build -p ios --profile production
```

After the build finishes, install the `.ipa` file via Xcode or TestFlight.

## Features

| Feature | Description |
|---|---|
| PDF Viewer | Native iOS PDF rendering via react-native-pdf |
| Text-to-Speech | On-device TTS with expo-speech (AVSpeechSynthesizer) |
| Speed Control | Adjust reading speed 0.5× – 2.0× |
| Bookmarks | Save & jump to bookmarked pages per document |
| Recent Files | Auto-tracks recently opened PDFs |
| Dark / Light | Follows iOS system appearance |
| Page Navigation | Previous / Next buttons + swipe gestures |

## Project Structure

```
mobile/
├── App.tsx                    # Root with navigation
├── src/
│   ├── screens/
│   │   ├── HomeScreen.tsx     # Welcome + recent files
│   │   └── ReaderScreen.tsx   # PDF reader + TTS
│   ├── components/
│   │   └── TTSControls.tsx    # TTS toolbar
│   ├── hooks/
│   │   ├── useTTS.ts          # TTS state (expo-speech)
│   │   ├── usePDFText.ts      # Text extraction (pdfjs-dist)
│   │   └── useRecentFiles.ts  # Recent files (AsyncStorage)
│   └── theme/
│       └── index.ts           # Colors + typography
```

## Dependencies

- **react-native-pdf** — PDF rendering (iOS PDFKit native)
- **expo-speech** — on-device TTS (iOS AVSpeechSynthesizer)
- **expo-document-picker** — iCloud / Files app integration
- **pdfjs-dist** — text extraction for TTS
- **@react-navigation/native** — screen navigation
- **@react-native-async-storage/async-storage** — bookmarks & recents
