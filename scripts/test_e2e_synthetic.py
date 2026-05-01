#!/usr/bin/env python3
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aggregator.server import CsiUdpServer
from processor.main import CsiProcessor
from detector.main import CsiDetector
from scripts.generate_synthetic_csi import make_csi_frame, build_scenario_fn

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

class TestHarness:
    def __init__(self, port=5007):
        self.port = port
        self.raw_queue = asyncio.Queue()
        self.feature_queue = asyncio.Queue()
        self.alert_queue = asyncio.Queue()
        self.server = CsiUdpServer(port=port, queue=self.raw_queue)
        self.processor = CsiProcessor(
            input_queue=self.raw_queue,
            output_queue=self.feature_queue,
            config={'window_size': 30, 'step_size': 15},
        )
        self.detector = CsiDetector(
            input_queue=self.feature_queue,
            output_queue=self.alert_queue,
            node_health_source={},
            config={
                'enter_frames': 2,
                'exit_frames': 3,
                'min_baseline_frames': 6,
                'baseline_alpha': 0.15,
                'baseline_skip_threshold_sigma': 2.0,
            },
        )
        self._alerts = []
        self._alert_task = None

    async def start(self):
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: self.server, local_addr=('127.0.0.1', self.port)
        )
        self.processor_task = asyncio.create_task(self.processor.run())
        self.detector_task = asyncio.create_task(self.detector.run())
        self._alert_task = asyncio.create_task(self._collect_alerts())
        await asyncio.sleep(0.3)

    async def _collect_alerts(self):
        while True:
            try:
                alert = await asyncio.wait_for(self.alert_queue.get(), timeout=0.5)
                self._alerts.append(alert)
            except asyncio.TimeoutError:
                continue

    async def send_scenario(self, scenario, duration, fps, node_id=1):
        amp_fn = build_scenario_fn(scenario)
        n_frames = int(duration * fps)
        interval = 1.0 / fps
        dest = ('127.0.0.1', self.port)
        t0 = time.monotonic()
        for seq in range(n_frames):
            t = seq * interval
            frame = make_csi_frame(node_id=node_id, sequence=seq, n_subcarriers=128, amplitude_fn=amp_fn, t=t)
            self.transport.sendto(frame, dest)
            expected = t0 + (seq + 1) * interval
            now = time.monotonic()
            sleep_for = expected - now
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

    async def stop(self):
        for task in [self.detector_task, self.processor_task, self._alert_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.transport.close()

    def report(self):
        total_frames = sum(n.frame_count for n in self.server.nodes.values())
        lines = [
            f'Raw frames received: {total_frames}',
            f'Features emitted: {self.feature_queue.qsize()}',
            f'Alerts fired: {len(self._alerts)}',
            '',
        ]
        for a in self._alerts:
            lines.append(
                f"  [t={a.get('timestamp', 0)}] node={a.get('node_id')} type={a.get('type')} status={a.get('status')} conf={a.get('confidence', 0):.2f}"
            )
        return "\n".join(lines)


async def test_empty_then_occupied():
    print('=' * 60)
    print('TEST: empty_then_occupied (30s empty -> 30s occupied -> 30s empty)')
    print('=' * 60)
    harness = TestHarness(port=5007)
    await harness.start()
    await harness.send_scenario('empty_then_occupied', duration=90, fps=10)
    await asyncio.sleep(2)
    await harness.stop()
    print(harness.report())
    statuses = [a['status'] for a in harness._alerts]
    occupied_idx = next((i for i, s in enumerate(statuses) if s == 'occupied'), None)
    empty_after_idx = next((i for i, s in enumerate(statuses) if s == 'empty' and occupied_idx is not None and i > occupied_idx), None)
    assert occupied_idx is not None, 'Should detect occupancy'
    assert empty_after_idx is not None, 'Should clear after person leaves'
    print('PASS: occupancy detected and cleared correctly.\n')


async def test_brief_visit():
    print('=' * 60)
    print('TEST: brief_visit (20s empty -> 10s occupied -> 20s empty)')
    print('=' * 60)
    harness = TestHarness(port=5008)
    await harness.start()
    await harness.send_scenario('brief_visit', duration=50, fps=10)
    await asyncio.sleep(2)
    await harness.stop()
    print(harness.report())
    statuses = [a['status'] for a in harness._alerts]
    occupied_idx = next((i for i, s in enumerate(statuses) if s == 'occupied'), None)
    empty_after_idx = next((i for i, s in enumerate(statuses) if s == 'empty' and occupied_idx is not None and i > occupied_idx), None)
    assert occupied_idx is not None, 'Should detect brief visit'
    assert empty_after_idx is not None, 'Should clear after brief visit'
    print('PASS: brief visit detected and cleared correctly.\n')


async def main():
    await test_empty_then_occupied()
    await test_brief_visit()
    print('All tests passed!')


if __name__ == '__main__':
    asyncio.run(main())