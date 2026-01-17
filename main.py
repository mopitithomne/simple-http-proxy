import socket
import select
import http.server
import socketserver
from urllib.parse import urlparse
from datetime import datetime
import threading
import time

tunnel_counter = 0
tunnel_lock = threading.Lock()

def next_tunnel_id():
    global tunnel_counter
    with tunnel_lock:
        tunnel_counter += 1
        return tunnel_counter

def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    timeout = 10

    def do_CONNECT(self):
        client_ip = self.client_address[0]
        host, port = self.path.split(":")
        port = int(port)

        tunnel_id = next_tunnel_id()
        start_time = time.time()

        log(f"[TUNNEL #{tunnel_id} OPEN] {client_ip} → {host}:{port}")

        try:
            remote = socket.create_connection((host, port), timeout=self.timeout)
        except OSError as e:
            log(f"[TUNNEL #{tunnel_id} ERROR] connect failed: {e}")
            self.send_error(502)
            return

        self.send_response(200, "Connection Established")
        self.end_headers()


        transferred = self._tunnel(tunnel_id, self.connection, remote)

        duration = time.time() - start_time
        log(
            f"[TUNNEL #{tunnel_id} CLOSE] "
            f"duration={duration:.2f}s "
            f"transferred={human_bytes(transferred)} "
            f"avg_rate={human_bytes(transferred / duration)}/s"
        )

    def do_GET(self):
        client_ip = self.client_address[0]

        if not self.path.startswith(("http://", "https://")):
            log(f"[REJECT] {client_ip} non-proxy request: {self.path}")
            self.send_error(400, "Absolute URI required")
            return

        parsed = urlparse(self.path)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        log(f"[HTTP] {client_ip} GET {self.path}")

        try:
            with socket.create_connection((host, port), timeout=self.timeout) as remote:
                remote.sendall(self._build_request())
                self._relay(remote)
        except OSError as e:
            log(f"[HTTP ERROR] {e}")
            self.send_error(502)

    def _build_request(self):
        req = f"{self.command} {self.path} HTTP/1.1\r\n"
        for k, v in self.headers.items():
            req += f"{k}: {v}\r\n"
        req += "\r\n"
        return req.encode()

    def _relay(self, remote):
        total = 0
        while True:
            data = remote.recv(8192)
            if not data:
                break
            total += len(data)
            self.wfile.write(data)
        log(f"[HTTP] response forwarded ({total} bytes)")


    def _tunnel(self, tunnel_id, client, remote):
        sockets = [client, remote]
        transferred = 0

        while True:
            try:
                readable, _, _ = select.select(sockets, [], [], self.timeout)
            except OSError:
                # select failed, likely because socket was closed unexpectedly
                break

            if not readable:
                break

            for s in readable:
                other = remote if s is client else client
                try:
                    data = s.recv(8192)
                    if not data:
                        return transferred
                    other.sendall(data)
                    transferred += len(data)
                except (ConnectionResetError, BrokenPipeError):
                    # socket was closed unexpectedly
                    log(f"[TUNNEL #{tunnel_id} ABORT] connection reset by peer after {human_bytes(transferred)}")
                    return transferred

        return transferred


    def log_message(self, *_):
        pass

class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

HOST_IP = 0.0.0.0
HOST_PORT = 8888

if __name__ == "__main__":
    log(f"Proxy HTTP/HTTPS démarré sur {HOST_IP}:{HOST_PORT}")
    with ThreadingTCPServer((HOST_IP, HOST_PORT), ProxyHandler) as server:
        server.serve_forever()
