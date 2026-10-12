import argparse
import functools
import http.server
import os
import subprocess
import sys
import threading
import time

BASE = os.path.dirname(os.path.abspath(__file__))
HLS = os.path.join(BASE, "hls")
os.makedirs(HLS, exist_ok=True)

opts = argparse.ArgumentParser()
opts.add_argument("--scale", default="1280x720",
                  help="Output resolution WxH (default 1280x720)")
opts.add_argument("--bitrate", default="1.5M",
                  help="Video bitrate, e.g. 1.5M (default 1.5M)")
args, _ = opts.parse_known_args()

FF_ARGS = [
    BASE + "/ffmpeg.exe",
    "-loglevel", "warning",
    "-i", "http://127.0.0.1:8090/live",
    "-vf", f"scale={args.scale}",
    "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
    "-b:v", args.bitrate, "-maxrate", args.bitrate, "-bufsize", "3M",
    "-g", "50", "-keyint_min", "50",
    "-force_key_frames", "expr:gte(t,n_forced*2)",
    "-f", "hls", "-hls_time", "2", "-hls_list_size", "6",
    "-hls_flags", "delete_segments+independent_segments",
    HLS + "/live.m3u8",
]

flog = open(BASE + "/demo_hls.log", "ab", buffering=0)


def spawn_segmenter():
    return subprocess.Popen(
        FF_ARGS,
        stdout=flog, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, close_fds=True,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )


state = {"proc": spawn_segmenter()}
print("HLS_FFMPEG_PID", state["proc"].pid, flush=True)


def _supervise():
    fails = 0
    while True:
        time.sleep(5)
        proc = state["proc"]
        if proc is not None and proc.poll() is None:
            fails = 0
            continue
        fails += 1
        wait = min(5 * fails, 30)
        flog.write(f"[host] segmenter exited (code {proc.returncode if proc else 'n/a'}); "
                   f"respawn in {wait}s (attempt {fails})\n".encode())
        flog.flush()
        time.sleep(wait)
        try:
            state["proc"] = spawn_segmenter()
            flog.write(f"[host] segmenter respawned pid={state['proc'].pid}\n".encode())
            flog.flush()
        except Exception as e:
            flog.write(f"[host] respawn failed: {e}\n".encode())
            flog.flush()


threading.Thread(target=_supervise, daemon=True).start()


# 2. static file server for the segments
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HLS, **kw)

    def log_message(self, *a):
        pass


Handler.extensions_map = {
    **http.server.SimpleHTTPRequestHandler.extensions_map,
    ".m3u8": "application/vnd.apple.mpegurl",
    ".ts": "video/mp2t",
}
srv = http.server.ThreadingHTTPServer(("0.0.0.0", 8091), Handler)
print("HLS_HTTP_READY", flush=True)


def _serve():
    srv.serve_forever()


import threading
t = threading.Thread(target=_serve, daemon=True)
t.start()

# keep this launcher alive briefly is NOT needed; detach server too is complex —
# instead just block here (this process becomes the server host, run detached by caller).
try:
    t.join()
except KeyboardInterrupt:
    pass
