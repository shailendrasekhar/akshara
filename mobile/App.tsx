import React from 'react';
import { NavigationContainer, DefaultTheme, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useColorScheme, StatusBar } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { HomeScreen } from './src/screens/HomeScreen';
import { ReaderScreen } from './src/screens/ReaderScreen';

export type RootStackParamList = {
  Home: undefined;
  Reader: {
    fileUri: string;
    fileName: string;
  };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function App() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';

  return (
    <SafeAreaProvider>
      <StatusBar
        barStyle={isDark ? 'light-content' : 'dark-content'}
        backgroundColor={isDark ? '#000000' : '#ffffff'}
      />
      <NavigationContainer theme={isDark ? DarkTheme : DefaultTheme}>
        <Stack.Navigator
          initialRouteName="Home"
          screenOptions={{
            headerStyle: {
              backgroundColor: isDark ? '#0a0a0a' : '#ffffff',
            },
            headerTintColor: isDark ? '#ffffff' : '#000000',
            headerTitleStyle: {
              fontWeight: '300',
              letterSpacing: 2,
            },
            contentStyle: {
              backgroundColor: isDark ? '#000000' : '#ffffff',
            },
          }}
        >
          <Stack.Screen
            name="Home"
            component={HomeScreen}
            options={{
              title: 'AKSHARA',
              headerLargeTitle: true,
            }}
          />
          <Stack.Screen
            name="Reader"
            component={ReaderScreen}
            options={({ route }) => ({
              title: route.params.fileName.replace('.pdf', ''),
              headerBackTitle: 'Library',
            })}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
