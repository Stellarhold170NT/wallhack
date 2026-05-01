# Coding Conventions

**Analysis Date:** 2026-05-01

## Naming Patterns

**Files:**
- PascalCase for React components: `ConnectionBanner.tsx`, `GaugeArc.tsx`, `SparklineChart.tsx`
- camelCase for utilities and services: `ringBuffer.ts`, `urlValidator.ts`, `colorMap.ts`
- Platform-specific suffix: `.android.ts`, `.ios.ts`, `.web.ts` (e.g., `rssi.service.android.ts`, `GaussianSplatWebView.web.tsx`)
- PascalCase for test files matching source: `ConnectionBanner.test.tsx`
- UPPER_SNAKE_CASE for constant files: `api.ts`, `websocket.ts`, `simulation.ts`

**Functions:**
- camelCase for all function names: `generateSimulatedData`, `validateServerUrl`, `valueToColor`
- React hooks prefixed with `use`: `usePoseStream`, `useTheme`, `useServerReachability`, `useRssiScanner`
- Event handlers prefixed with `handle`: `handleFrame`, `handleReady`, `handleFps`, `handleError`, `handleRetry`
- Private class methods prefixed with `private` keyword in TypeScript: `buildWsUrl`, `scheduleReconnect`, `handleStatusChange`
- Factory functions: `makeFrame()`, `makeEvent()`, `makeSurvivor()` in test files

**Variables:**
- camelCase throughout: `connectionStatus`, `messageCount`, `rssiHistory`, `serverUrl`
- Boolean prefixes: `isSimulated`, `isPresent`, `isActive`, `isDark`, `hasError`, `hasNavigation`
- Const enums and constants in UPPER_SNAKE_CASE: `MAX_RSSI_HISTORY`, `SIMULATION_TICK_INTERVAL_MS`, `WS_PATH`

**Types:**
- PascalCase for interfaces: `SensingFrame`, `FeatureSet`, `Classification`, `SignalField`, `PoseState`
- PascalCase for TypeScript type aliases: `ConnectionStatus`, `LiveMode`, `TextPreset`, `ColorKey`
- PascalCase for enums: `DisasterType`, `TriageStatus`, `ZoneStatus`, `AlertPriority`
- Interface naming: follows pattern `<Noun>Props` for component props: `GaugeArcProps`, `ConnectionBannerProps`, `ErrorBoundaryProps`
- Interface naming: follows pattern `<Store>State` for Zustand store types: `PoseState`, `MatState`, `SettingsState`
- Return types: `UsePoseStreamResult` for hook return interfaces

## Code Style

**Formatting:**
- Prettier with `singleQuote: true` and `trailingComma: 'all'` (config in `.prettierrc`)
- Double quotes only in JSX attributes (enforced by Prettier not configuring `jsxSingleQuote`)

**Linting:**
- ESLint via `@typescript-eslint/parser` (TypeScript 5.9)
- `eslint:recommended` + `plugin:react/recommended` + `plugin:react-hooks/recommended` + `plugin:@typescript-eslint/recommended`
- Custom rule: `react/react-in-jsx-scope: 'off'` (React 19 doesn't need JSX import)

**TypeScript Configuration:**
- `tsconfig.json` extends `expo/tsconfig.base` with `strict: true`
- Path alias `@/*` maps to `./src/*`
- All imports use the `@/` alias for internal modules

**Async Patterns:**
- `async/await` for Promise-based code (e.g., `api.service.ts` uses `async requestWithRetry`)
- `.then()` and `.catch()` only for dynamic imports in components: `import('./GaussianSplatWebView.web').then((mod) => ...)`
- `void` operator for fire-and-forget promises: `void readThemeFromSettings().then(setThemeMode)`

**React Patterns:**
- Functional components with hooks (no class components except `ErrorBoundary`)
- `useCallback` for memoized event handlers passed as props
- `useMemo` for derived data (normalized values, chart data)
- `useEffect` for side effects (lifecycle, subscriptions, async init)
- `useRef` for mutable refs (WebView refs, timer IDs)
- `useState` for local component state
- Lazy loading via `React.lazy()` with `Suspense`
- Dynamic import with `require()` in try-catch for native module fallbacks

## Import Organization

**Order:**
1. React / React Native core imports
2. Third-party libraries (axios, zustand, expo, react-navigation, react-native-svg, react-native-reanimated)
3. Internal `@/` aliased imports (stores, services, hooks, components, types, utils, constants)
4. Local relative imports (same-directory files: `./GaussianSplatWebView`, `./LiveHUD`)

**Path Aliases:**
- `@/*` → `./src/*` (configured in `tsconfig.json` paths)

**Examples:**
```typescript
import { useEffect, useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { useAnimatedProps, useSharedValue, withSpring } from 'react-native-reanimated';
import Svg, { Circle, G, Text as SvgText } from 'react-native-svg';
import { create } from 'zustand';
import { RingBuffer } from '@/utils/ringBuffer';
import type { Classification, ConnectionStatus, SensingFrame } from '@/types/sensing';
```

## Error Handling

**Patterns:**
- `try-catch` for external operations (WebSocket messages, Axios calls, JSON parsing, dynamic imports)
- Empty `catch {}` for expected-rare failures where recovery isn't needed (malformed WebSocket frame, ignore)
- `catch` with logging for recoverable errors: `console.error('ErrorBoundary caught an error', error, errorInfo)`
- `catch` with state fallback for feature-level failures (set error state for UI display)
- `ErrorBoundary` React class component at screen level wrapping fallible render trees
- `normalizeError()` method in API service classifying Axios vs generic vs unknown errors
- Zustand stores don't throw — error handling delegated to services and UI

**Error Types:**
```typescript
// API service error normalization pattern (src/services/api.service.ts)
private normalizeError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) { /* extract message from response */ }
  if (error instanceof Error) { return { message: error.message }; }
  return { message: 'Unknown error' };
}
```

```typescript
// ErrorBoundary pattern (src/components/ErrorBoundary.tsx)
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, errorInfo: ErrorInfo) { /* log */ }
  handleRetry = () => { this.setState({ hasError: false, error: undefined }); };
}
```

## Logging

**Framework:** `console` (no external logging library)

**Patterns:**
- `console.error()` in error boundaries
- `logger.warning()` in Python aggregator via standard logging module
- Minimal console usage in production code — errors propagate via return values

## Comments

**When to Comment:**
- Interface/type documentation for public types: `/** Estimated person count from CSI feature heuristics (1-3 for single ESP32). */`
- Complex logic sections in services: `// Auto-connect to sensing server on mount`
- Test comments explaining what a test group covers
- Module-level docstrings in Python: `"""Unit tests for CSI binary frame parser (Wave 1)."""`
- Architecture references: `// Ref: ADR-018, firmware/esp32-csi-node/main/csi_collector.c`
- Edge case explanations: `// GaugeArc uses Animated.createAnimatedComponent(Circle), so we need the reanimated mock`

**JSDoc/TSDoc:**
- Used for public function documentation: `@param`, `@returns` in Python docstrings
- Minimal in TypeScript — inline comments preferred
- Return type annotations used instead of JSDoc `@returns`

## Function Design

**Size:**
- Utility functions: 5-25 lines (single responsibility)
- Service methods: 5-50 lines
- React component render: 20-80 lines
- Complex algorithms: up to 100 lines (e.g., `generateSimulatedData` in `simulation.service.ts`)

**Parameters:**
- Named parameters through destructured props objects for components: `type GaugeArcProps = { value: number; max: number; ... }`
- Simple parameters for utility functions: `function gaussian(x: number, y: number, cx: number, cy: number, sigma: number): number`
- Overrides pattern in factories: `const makeFrame = (overrides: Partial<SensingFrame> = {}): SensingFrame => ({ ...defaults, ...overrides })`

**Return Values:**
- Typed return values always specified: `function validateServerUrl(url: string): UrlValidationResult`
- `null` for "not found" or "not available" states
- Consistent object shape returns for validation: `{ valid: boolean; error?: string }`
- API methods return typed `Promise<T>`
- Hook return types as interfaces: `UsePoseStreamResult`

## Module Design

**Exports:**
- Named exports for all components: `export const ConnectionBanner = ...`
- Named exports for all functions and hooks: `export function usePoseStream()`
- Named exports for Zustand stores: `export const usePoseStore = create<PoseState>(...)`
- Default export for screen components as alias: `export default LiveScreen` alongside named export
- Barrel export in theme: `src/theme/index.ts` re-exports `colors`, `spacing`, `typography`

**Barrel Files:**
- `src/theme/index.ts` — re-exports theme modules
- Other directories use direct imports rather than barrel files

## State Management

**Zustand Stores:**
- Store created with `create<StateType>()()` pattern
- `persist` middleware for settings: `create<SettingsState>()(persist((set) => ({...}), { name, storage }))`
- Selector-based access in hooks: `usePoseStore((state) => state.connectionStatus)`
- Direct access for tests: `usePoseStore.getState()`
- Reset implemented as explicit method setting all fields to defaults
- Side-effect-free stores (no async actions in store)
- All stores use named interfaces for state shape

## Component Architecture

**Screen structure:**
- Each screen in `src/screens/<ScreenName>/` directory
- `index.tsx` is the main screen component
- Sub-components in same directory: `LiveHUD.tsx`, `GaussianSplatWebView.tsx`
- Platform-specific files: `GaussianSplatWebView.tsx` (native) + `GaussianSplatWebView.web.tsx` (web)

**Platform-specific code:**
- Runtime platform checks: `Platform.OS === 'web'` for render branching
- File suffix convention: `.android.ts`, `.ios.ts`, `.web.ts`
- `require()` in try-catch for native-only modules

## Constants and Configuration

**Constants files:**
- `src/constants/api.ts` — REST API paths as `UPPER_SNAKE_CASE`
- `src/constants/websocket.ts` — WebSocket config values
- `src/constants/simulation.ts` — Simulation parameters

All constants are `export const` with explicit type inference.

---

*Convention analysis: 2026-05-01*
