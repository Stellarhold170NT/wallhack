"""CLI entry point for the CSI UDP Aggregator.

Starts the asyncio UDP server, writes .npy amplitude data to disk,
and orchestrates the consumer loop that bridges server → writer.
Optionally wires in the CsiProcessor for real-time signal processing.

Usage:
    python -m aggregator --port 5005
    python -m aggregator --port 5005 --output-dir data/my_session --buffer-capacity 1000
"""

import asyncio
import argparse
import logging
import signal
from .server import CsiUdpServer
from .persistence import NpyWriter

logger = logging.getLogger("aggregator")


def _load_processor() -> type | None:
    """Import CsiProcessor if available, else return None."""
    try:
        from processor.main import CsiProcessor
        return CsiProcessor
    except ImportError as exc:
        logger.warning("CsiProcessor not available: %s", exc)
        return None


async def run_server(args: argparse.Namespace) -> None:
    raw_queue: asyncio.Queue = asyncio.Queue()
    feature_queue: asyncio.Queue = asyncio.Queue()
    server = CsiUdpServer(
        port=args.port,
        queue=raw_queue,
        buffer_capacity=args.buffer_capacity,
    )
    writer = NpyWriter(
        output_dir=args.output_dir,
        rotation_frames=args.rotation_frames,
    )

    CsiProcessor = _load_processor()
    processor = None
    processor_task = None
    if CsiProcessor is not None:
        config = {}
        if args.processor_config:
            import json
            config = json.loads(args.processor_config)
        processor = CsiProcessor(
            input_queue=raw_queue,
            output_queue=feature_queue,
            config=config,
        )

    consumer_task: asyncio.Task | None = None
    shutdown_event = asyncio.Event()

    async def consumer() -> None:
        try:
            while True:
                frame = await raw_queue.get()
                writer.write(frame)
        except asyncio.CancelledError:
            pass

    async def shutdown() -> None:
        if shutdown_event.is_set():
            return
        shutdown_event.set()
        logger.info("Shutting down...")
        if processor_task and not processor_task.done():
            processor_task.cancel()
            try:
                await processor_task
            except asyncio.CancelledError:
                pass
        if consumer_task and not consumer_task.done():
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass
        await server.stop()
        writer.flush_all()
        logger.info("Shutdown complete.")

    loop = asyncio.get_running_loop()

    def _sigint_handler() -> None:
        asyncio.create_task(shutdown())

    try:
        loop.add_signal_handler(signal.SIGINT, _sigint_handler)
    except NotImplementedError:
        pass

    try:
        loop.add_signal_handler(signal.SIGTERM, _sigint_handler)
    except NotImplementedError:
        pass

    try:
        await server.start()
        consumer_task = asyncio.create_task(consumer())
        if processor is not None:
            processor_task = asyncio.create_task(processor.run())
            logger.info("CsiProcessor wired into pipeline")
        logger.info("Aggregator running on UDP port %d", args.port)
        await shutdown_event.wait()
    finally:
        await shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CSI UDP Aggregator — receives CSI frames from ESP32-S3 nodes"
    )
    parser.add_argument(
        "--port", type=int, default=5005, help="UDP port to listen on (default: 5005)"
    )
    parser.add_argument(
        "--buffer-capacity",
        type=int,
        default=500,
        help="Max frames per node before dropping oldest (default: 500)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/raw",
        help="Root directory for .npy output (default: data/raw)",
    )
    parser.add_argument(
        "--rotation-frames",
        type=int,
        default=10000,
        help="Frames per .npy file before auto-rotation (default: 10000)",
    )
    parser.add_argument(
        "--processor-config",
        type=str,
        default="",
        help='JSON config dict for CsiProcessor (e.g., \'{"window_size":100}\')',
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(run_server(args))


if __name__ == "__main__":
    main()
