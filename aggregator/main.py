"""CLI entry point for the CSI UDP Aggregator.

Starts the asyncio UDP server, writes .npy amplitude data to disk,
and orchestrates the consumer loop that bridges server → writer.

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


async def run_server(args: argparse.Namespace) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    server = CsiUdpServer(
        port=args.port,
        queue=queue,
        buffer_capacity=args.buffer_capacity,
    )
    writer = NpyWriter(
        output_dir=args.output_dir,
        rotation_frames=args.rotation_frames,
    )

    consumer_task: asyncio.Task | None = None
    shutdown_event = asyncio.Event()

    async def consumer() -> None:
        while True:
            frame = await queue.get()
            writer.write(frame)

    async def shutdown() -> None:
        if shutdown_event.is_set():
            return
        shutdown_event.set()
        logger.info("Shutting down...")
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
        asyncio.ensure_future(shutdown())

    try:
        loop.add_signal_handler(signal.SIGINT, _sigint_handler)
    except NotImplementedError:

        loop.call_soon(lambda: None)

    try:
        loop.add_signal_handler(signal.SIGTERM, _sigint_handler)
    except NotImplementedError:

        loop.call_soon(lambda: None)

    await server.start()
    consumer_task = asyncio.create_task(consumer())
    logger.info("Aggregator running on UDP port %d", args.port)

    await shutdown_event.wait()

    logger.info("Aggregator stopped.")


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

    try:
        asyncio.run(run_server(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
