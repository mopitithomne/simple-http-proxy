# simple-http-proxy

Goal
- Provide a minimal, single-file HTTP/HTTPS proxy for local testing and inspection.

What it does
- Handles CONNECT tunnels for HTTPS.
- Forwards absolute-URI HTTP requests.
- Logs connection open/close, transfer volumes and rates.
- Handles multiple clients with threads.

Quick usage
- Run the proxy:
    ```
    python main.py
    ```
- Point your client/browser at 127.0.0.1:8888 and use it as an HTTP/HTTPS proxy.


Notes
- Configure your client/browser to use the proxy as HTTP/HTTPS proxy.
- Logs are printed on the console.