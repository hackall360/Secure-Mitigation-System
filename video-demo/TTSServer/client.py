# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Speak one line through the local video-demo TTS server.

Usage:
    python client.py "Your narration line." [--host 127.0.0.1] [--port 8002]
    python client.py --render "Your line." --out line.wav [--host ...] [--port ...]

`/speak` queues for background generation + speaker playback (non-blocking).
`--render` synthesiszes synchronously and saves a 24 kHz WAV for the video
pipeline. Both fail closed with an explicit message when the server is down.
"""

import argparse
import sys
import urllib.request


def post_json(base, path, payload, timeout=30):
    import json

    data = json.dumps(payload).encode()
    request = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        body = response.read()
        ctype = response.headers.get_content_type()
        if ctype == "application/json":
            return response.status, json.loads(body)
        return response.status, body


def main(argv=None):
    parser = argparse.ArgumentParser(description="Talk to the local TTS server")
    parser.add_argument("text", help="Narration line to speak or render")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument(
        "--render", action="store_true", help="save WAV instead of queueing playback"
    )
    parser.add_argument("--out", default="line.wav", help="output path for --render")
    args = parser.parse_args(argv)
    base = f"http://{args.host}:{args.port}"
    try:
        if args.render:
            status, body = post_json(base, "/render", {"text": args.text}, timeout=300)
            if status != 200 or not isinstance(body, bytes):
                raise RuntimeError(f"Unexpected render response (HTTP {status}).")
            with open(args.out, "wb") as fh:
                fh.write(body)
            print(f"saved {args.out} ({len(body)} bytes)")
        else:
            status, body = post_json(base, "/speak", {"text": args.text})
            if status != 200:
                raise RuntimeError(f"Unexpected speak response (HTTP {status}).")
            print(body)
    except OSError as exc:
        print(f"TTS server unreachable at {base}: {exc}", file=sys.stderr)
        print("Start it first: ./start.sh (or: python server.py)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
