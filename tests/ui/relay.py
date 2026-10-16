"""Relais du banc, comme « tailscale serve » devant le Mac : lancé par driver.mjs (startBench({ relay: true })), jamais
à la main en temps normal.

Écoute sur un port libre de 127.0.0.1 et relaie chaque requête vers le serveur du banc (premier argument) en lui
donnant ce que le serveur voit d'un téléphone passé par Tailscale : Host égal au nom HTTPS (second argument),
X-Forwarded-For d'un autre appareil, Origin https://<nom>. Écrit son port sur une ligne, puis tourne jusqu'à la
fermeture de son entrée standard (fin du test, ou test tué).
"""
import http.server, os, socketserver, sys, threading, urllib.error, urllib.request

TARGET, HOST = sys.argv[1].rstrip("/"), sys.argv[2]
DROPPED = ("host", "origin", "content-length", "connection")                 # en-têtes refaits par le relais
NOT_COPIED = ("content-length", "connection", "transfer-encoding", "date", "server")


class Relay(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def relay(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in DROPPED}
        headers["Host"], headers["X-Forwarded-For"] = HOST, "192.0.2.10"   # adresse de documentation (RFC 5737)
        if self.headers.get("Origin"):
            headers["Origin"] = "https://" + HOST
        request = urllib.request.Request(TARGET + self.path, data=body, headers=headers, method=self.command)
        try:
            reply = urllib.request.urlopen(request, timeout=30)   # serveur bloqué : le test échoue, sans attendre
        except urllib.error.HTTPError as e:                  # 4xx et 5xx : relayés tels quels
            reply = e
        data = reply.read()
        self.send_response(reply.status)
        for k, v in reply.headers.items():
            if k.lower() not in NOT_COPIED:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = relay


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


server = Server(("127.0.0.1", 0), Relay)
print(server.server_address[1], flush=True)
threading.Thread(target=server.serve_forever, daemon=True).start()
sys.stdin.read()
os._exit(0)
