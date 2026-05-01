# Testing Patterns

**Analysis Date:** 2026-05-01

## Test Framework

**Runner:**
- **TypeScript/React Native:** Jest v30 with `jest-expo` preset
  - Config: `llm-wiki/raw/RuView/ui/mobile/jest.config.js`
  - Preset: `jest-expo` (handles Expo module transformation)
  - Transform ignore: `node_modules/(?!(expo|expo-.+|react-native|...)/)` pattern for RN packages

- **Python (aggregator):** pytest v7+
  - Config: `requirements.txt` includes `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`
  - Run: `python -m pytest aggregator/`

- **Rust (v2 crates):** Rust built-in test framework + `cargo test`
  - Benches via `cargo bench`

**Assertion Library:**
- TypeScript: Jest built-in matchers + `@testing-library/react-native` queries
- Python: `pytest` native asserts + `pytest.approx()`
- Rust: Standard `assert_eq!`, `assert!` macros

**Run Commands:**
```bash
# TypeScript (mobile)
cd llm-wiki/raw/RuView/ui/mobile
npm test                      # Run all Jest tests
npx jest --watch              # Watch mode
npx jest --coverage           # Coverage report

# Python (aggregator)
python -m pytest aggregator/ -v  # Run all aggregator tests

# Rust (v2)
cd llm-wiki/raw/RuView/v2
cargo test --workspace --no-default-features  # All Rust tests
cargo bench -p wifi-densepose-signal          # Signal benchmarks
```

## Test File Organization

**Location:**
- TypeScript: Co-located in `src/__tests__/` mirroring source directory structure
- Python: Same directory as source files (`test_parser.py` alongside `parser.py`)
- Rust: Integration tests in `tests/` directory within each crate

**Naming:**
- TypeScript: `*.test.ts` for pure logic, `*.test.tsx` for React components/screens
- Python: `test_*.py` naming convention
- Rust: `*_test.rs` for integration tests, `#[cfg(test)] mod tests` for unit tests

**Structure:**
```
src/__tests__/
├── components/         # Component tests (7 files)
│   ├── ConnectionBanner.test.tsx
│   ├── GaugeArc.test.tsx
│   ├── HudOverlay.test.tsx
│   ├── OccupancyGrid.test.tsx
│   ├── SignalBar.test.tsx
│   ├── SparklineChart.test.tsx
│   └── StatusDot.test.tsx
├── hooks/              # Hook tests (3 files)
│   ├── usePoseStream.test.ts
│   ├── useRssiScanner.test.ts
│   └── useServerReachability.test.ts
├── screens/            # Screen tests (5 files)
│   ├── LiveScreen.test.tsx
│   ├── MATScreen.test.tsx
│   ├── SettingsScreen.test.tsx
│   ├── VitalsScreen.test.tsx
│   └── ZonesScreen.test.tsx
├── services/           # Service tests (4 files)
│   ├── api.service.test.ts
│   ├── rssi.service.test.ts
│   ├── simulation.service.test.ts
│   └── ws.service.test.ts
├── stores/             # Store tests (3 files)
│   ├── matStore.test.ts
│   ├── poseStore.test.ts
│   └── settingsStore.test.ts
├── utils/              # Utility tests (3 files)
│   ├── colorMap.test.ts
│   ├── ringBuffer.test.ts
│   └── urlValidator.test.ts
├── test-utils.tsx      # Shared test helpers
└── __mocks__/          # Manual module mocks
    ├── getBundleUrl.js
    └── importMetaRegistry.js
```

## Test Structure

**Suite Organization:**
```typescript
describe('ComponentName', () => {
  describe('method/feature', () => {
    it('describes expected behavior', () => {
      // Arrange
      // Act
      // Assert
    });
  });
});
```

**Patterns:**
- Nested `describe` blocks for methods/features — 2 levels deep common
- `it('describes expected behavior')` using natural language
- `beforeEach` for state reset: `usePoseStore.getState().reset()`, `useSettingsStore.setState({defaults})`, `jest.useFakeTimers()`
- `afterEach` for cleanup: `jest.useRealTimers()`
- Pure logic tests use direct imports. Component tests use `require()` for mocked modules.

**Setup pattern:**
```typescript
// jest.setup.ts — global mocks for native modules
jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock')
);
jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-webview', () => { /* mock WebView as View */ });
jest.mock('react-native-wifi-reborn', () => ({ loadWifiList: jest.fn(async () => []) }));
```

## Mocking

**Framework:** Jest native mocking (`jest.mock`, `jest.fn`, `jest.spyOn`)

**Patterns:**
```typescript
// External module mock at top of test file
jest.mock('@/services/ws.service', () => ({
  wsService: {
    subscribe: jest.fn(() => jest.fn()),
    connect: jest.fn(),
    disconnect: jest.fn(),
    getStatus: jest.fn(() => 'disconnected'),
  },
}));

// Axios module mock with instance
jest.mock('axios', () => {
  const mockAxiosInstance = { request: jest.fn() };
  return { create: jest.fn(() => mockAxiosInstance), isAxiosError: jest.fn(), __mockInstance: mockAxiosInstance };
});

// Native module mock (react-native-svg)
jest.mock('react-native-svg', () => {
  const { View } = require('react-native');
  return { __esModule: true, default: View, Svg: View, Circle: View, G: View, Text: View, Rect: View };
});

// Hook mock for screen tests
jest.mock('@/hooks/usePoseStream', () => ({
  usePoseStream: () => ({ connectionStatus: 'simulated', lastFrame: null, isSimulated: true }),
}));
```

**What to Mock:**
- Native modules (react-native-svg, react-native-reanimated, react-native-webview)
- Services that create side effects (ws.service, simulation.service)
- External libraries (axios, AsyncStorage)
- Module-level dependencies for hooks

**What NOT to Mock:**
- Pure utility functions tested directly
- Zustand stores (tested via `getState()` / `setState()` directly)
- Type-only imports

**Mock isolation technique:**
```typescript
function createWsService() {
  let service: any;
  jest.isolateModules(() => {
    service = require('@/services/ws.service').wsService;
  });
  return service;
}
```

## Fixtures and Factories

**Test Data:**
```typescript
// Factory pattern with Partial overrides (src/__tests__/stores/poseStore.test.ts)
const makeFrame = (overrides: Partial<SensingFrame> = {}): SensingFrame => ({
  type: 'sensing_update',
  timestamp: Date.now(),
  source: 'simulated',
  nodes: [{ node_id: 1, rssi_dbm: -45, position: [0, 0, 0] }],
  features: { mean_rssi: -45, variance: 1.5, motion_band_power: 0.1, breathing_band_power: 0.05, spectral_entropy: 0.8 },
  classification: { motion_level: 'present_still', presence: true, confidence: 0.85 },
  signal_field: { grid_size: [20, 1, 20], values: new Array(400).fill(0.5) },
  ...overrides,
});

// MAT domain factories (src/__tests__/stores/matStore.test.ts)
const makeEvent = (overrides: Partial<DisasterEvent> = {}): DisasterEvent => ({ ...defaults, ...overrides });
const makeZone = (overrides: Partial<ScanZone> = {}): ScanZone => ({ ...defaults, ...overrides });
const makeSurvivor = (overrides: Partial<Survivor> = {}): Survivor => ({ ...defaults, ...overrides });
const makeAlert = (overrides: Partial<Alert> = {}): Alert => ({ ...defaults, ...overrides });
```

**Location:**
- Factory functions defined locally in each test file (not shared)
- Manual module mocks in `src/__tests__/__mocks__/` for Expo runtime globals
- Shared providers and render helpers in `src/__tests__/test-utils.tsx`

## Coverage

**Requirements:** None enforced (no `--coverage` threshold in config)

**View Coverage:**
```bash
npx jest --coverage
```

**Coverage by category (25 test files total):**
| Category | Files | Test Count Estimate |
|----------|-------|-------------------|
| Components | 7 | ~25 tests |
| Screens | 5 | ~25 tests |
| Services | 4 | ~35 tests |
| Stores | 3 | ~55 tests |
| Hooks | 3 | ~12 tests |
| Utils | 3 | ~30 tests |
| **Total** | **25** | **~180+ tests** |

## Test Types

**Unit Tests:**
- Pure logic: `ringBuffer.test.ts`, `colorMap.test.ts`, `urlValidator.test.ts` — test all edge cases
- State stores: `poseStore.test.ts`, `matStore.test.ts`, `settingsStore.test.ts` — test initial state, all actions, reset
- Services: `simulation.service.test.ts`, `api.service.test.ts` — test all methods, retries, error normalization
- Component tests verify rendering without crashing and correct text output
- Hook tests verify module exports and interface shape (limited by inability to call hooks outside render)

**Integration Tests:**
- `ws.service.test.ts` — tests WebSocket connection, reconnect logic, simulation fallback with mocked WebSocket and timers
- `api.service.test.ts` — tests retry logic, error normalization, URL building with mocked Axios

**E2E Tests:**
- Maestro YAML specs in `ui/mobile/e2e/`
- Screens: `live_screen.yaml`, `vitals_screen.yaml`, `zones_screen.yaml`, `mat_screen.yaml`, `settings_screen.yaml`, `offline_fallback.yaml`
- Maestro config in `e2e/.maestro/config.yaml` (empty — defaults)
- Currently test files appear to be empty stubs (0 bytes)

**Python Tests (aggregator):**
- Class-based test organization: `TestParseValidFrame`, `TestParseInvalidFrame`, `TestAmplitudePhase`, `TestCorruptedFrame`, `TestCSIFrameDataclass`
- `pytest` parameterization for edge cases
- Factory helper pattern: `build_frame()` constructs test data
- Fuzz testing: `test_parse_1000_random_frames_no_crash`
- Async test via `@pytest.mark.asyncio` for UDP server tests

**Rust Tests (v2 crates):**
- Integration tests in `tests/` directories per crate
- `cargo test --workspace --no-default-features` runs all
- Feature-flagged tests: `--features std` for WASM edge module tests
- Benchmarks via `cargo bench` in `benches/` directories
- 542+ tests across the workspace per crate documentation

## Common Patterns

**Async Testing:**
```typescript
// Jest fake timers for interval-based services
beforeEach(() => { jest.useFakeTimers(); });
afterEach(() => { jest.useRealTimers(); });

test('simulation emits frames', () => {
  ws.connect('');
  jest.advanceTimersByTime(600);  // Simulate 600ms
  expect(listener).toHaveBeenCalled();
});
```

```typescript
// Promise-based async tests
it('returns response data on success', async () => {
  mockRequest.mockResolvedValueOnce({ data: { status: 'ok' } });
  const result = await apiService.get('/api/v1/pose/status');
  expect(result).toEqual({ status: 'ok' });
});
```

**Error Testing:**
```typescript
it('normalizes axios error with response data message', async () => {
  const axiosError = { message: 'Request failed', response: { status: 400, data: { message: 'Bad request' } }, isAxiosError: true };
  mockRequest.mockRejectedValue(axiosError);
  (mockAxios.isAxiosError as jest.Mock).mockReturnValue(true);
  await expect(apiService.get('/test')).rejects.toEqual(
    expect.objectContaining({ message: 'Bad request', status: 400 })
  );
});
```

```typescript
it('retries up to 2 times on failure then throws', async () => {
  mockRequest.mockRejectedValue(new Error('fail'));
  await expect(apiService.get('/flaky')).rejects.toEqual(
    expect.objectContaining({ message: 'fail' })
  );
  expect(mockRequest).toHaveBeenCalledTimes(3);  // 1 initial + 2 retries
});
```

**Store Testing Pattern:**
```typescript
describe('usePoseStore', () => {
  beforeEach(() => { usePoseStore.getState().reset(); });

  it('updates features from frame', () => {
    const frame = makeFrame();
    usePoseStore.getState().handleFrame(frame);
    expect(usePoseStore.getState().features).toEqual(frame.features);
  });
});
```

**Component Rendering Pattern:**
```typescript
import { render, screen } from '@testing-library/react-native';
import { ThemeProvider } from '@/theme/ThemeContext';

const renderWithTheme = (ui: React.ReactElement) =>
  render(<ThemeProvider>{ui}</ThemeProvider>);

it('renders LIVE STREAM text when connected', () => {
  renderWithTheme(<ConnectionBanner status="connected" />);
  expect(screen.getByText('LIVE STREAM')).toBeTruthy();
});
```

**Shared Test Provider Pattern:**
```typescript
// src/__tests__/test-utils.tsx
export const renderWithProviders = (
  ui: React.ReactElement,
  { withNavigation, ...options }: RenderWithProvidersOptions = {},
) => {
  return render(ui, {
    ...options,
    wrapper: withNavigation ? TestProvidersWithNavigation : TestProviders,
  });
};
```

**WebSocket Mocking Pattern:**
```typescript
class MockWebSocket {
  static OPEN = 1; static CONNECTING = 0;
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
  constructor(url: string) { capturedUrls.push(url); }
}
globalThis.WebSocket = MockWebSocket as any;
```

---

*Testing analysis: 2026-05-01*
