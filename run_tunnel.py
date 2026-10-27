import os
import sys
import re
import time
import signal
import subprocess
import threading

def stream_reader(pipe, is_tunnel=False):
    pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    while True:
        line = pipe.readline()
        if not line:
            break
        decoded = line.strip()
        if is_tunnel:
            match = pattern.search(decoded)
            if match:
                url = match.group(0)
                print("\n" + "=" * 80)
                print(f" PUBLIC API URL: {url}")
                print(f" SWAGGER DOCS:   {url}/docs")
                print(f" HEALTH CHECK:   {url}/health")
                print(f" GENERATE:       {url}/api/v1/generate")
                print("=" * 80 + "\n", flush=True)
        else:
            print(decoded, flush=True)

def main():
    api_cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
    tunnel_cmd = ["cloudflared", "tunnel", "--url", "http://127.0.0.1:8000"]

    print("Starting local API server and Cloudflare tunnel...", flush=True)

    api_proc = subprocess.Popen(
        api_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    tunnel_proc = subprocess.Popen(
        tunnel_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    t1 = threading.Thread(target=stream_reader, args=(api_proc.stdout, False), daemon=True)
    t2 = threading.Thread(target=stream_reader, args=(tunnel_proc.stdout, True), daemon=True)
    t1.start()
    t2.start()

    def handle_exit(sig, frame):
        print("\nStopping server and tunnel...", flush=True)
        try:
            api_proc.terminate()
        except Exception:
            pass
        try:
            tunnel_proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        while True:
            if api_proc.poll() is not None or tunnel_proc.poll() is not None:
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        handle_exit(None, None)

if __name__ == "__main__":
    main()
