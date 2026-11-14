"""Serve the repo root so the UI can read ../runs/*. Usage: python ui/serve.py  ->  http://localhost:8000/ui/
Optional: ?run=runs/gate to pick a specific run directory."""
import functools
import http.server
import os

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
print("Stego UI: http://localhost:8000/ui/")
http.server.ThreadingHTTPServer(("127.0.0.1", 8000), handler).serve_forever()
