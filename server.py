from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sqlite3
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import os

DB_PATH = "wallet.db"

# === Datenbank initialisieren ===
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            balance REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_wallet TEXT,
            to_wallet TEXT,
            amount REAL NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# === HTTP Server ===
class WalletHandler(BaseHTTPRequestHandler):

    
    
    def _set_headers(self, code=200, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_json(self, data, code=200):
        self._set_headers(code)
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        return json.loads(body) if body else {}

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        if path == "/api/health":
            self._send_json({
                "status": "ok",
                "time": datetime.now().isoformat()
            })
            return

    def do_OPTIONS(self):
        self._set_headers()

    # --- Wallet-Liste abrufen ---
    def handle_get_wallets(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name, balance, created_at FROM wallets")
        rows = c.fetchall()
        conn.close()
        wallets = [{"name": r[0], "balance": r[1], "created_at": r[2]} for r in rows]
        self._send_json(wallets)

    # --- Transaktionshistorie abrufen (optional nach Wallet gefiltert) ---
    def handle_get_transactions(self, query_params):
        wallet_name = query_params.get("wallet", [None])[0]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        if wallet_name:
            c.execute("""
                SELECT from_wallet, to_wallet, amount, timestamp
                FROM transactions
                WHERE from_wallet = ? OR to_wallet = ?
                ORDER BY id DESC
            """, (wallet_name, wallet_name))
        else:
            c.execute("SELECT from_wallet, to_wallet, amount, timestamp FROM transactions ORDER BY id DESC")

        rows = c.fetchall()
        conn.close()

        transactions = [
            {"from": r[0], "to": r[1], "amount": r[2], "timestamp": r[3]}
            for r in rows
        ]
        self._send_json(transactions)

    # --- Wallet erstellen ---
    def handle_create_wallet(self, data):
        name = data.get("name")
        if not name:
            self._send_json({"error": "Wallet-Name fehlt"}, 400)
            return

        now = datetime.now().isoformat()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO wallets (name, balance, created_at) VALUES (?, ?, ?)", (name, 100.0, now))
            conn.commit()
            result = {"name": name, "balance": 100.0, "created_at": now}
            self._send_json(result, 201)
        except sqlite3.IntegrityError:
            self._send_json({"error": "Wallet-Name existiert bereits"}, 409)
        conn.close()

    # --- Transaktion durchführen ---
    def handle_create_transaction(self, data):
        from_wallet = data.get("from")
        to_wallet = data.get("to")
        amount = float(data.get("amount", 0))

        if not from_wallet or not to_wallet or amount <= 0:
            self._send_json({"error": "Ungültige Transaktionsdaten"}, 400)
            return

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Guthaben prüfen
        c.execute("SELECT balance FROM wallets WHERE name = ?", (from_wallet,))
        sender = c.fetchone()
        c.execute("SELECT balance FROM wallets WHERE name = ?", (to_wallet,))
        receiver = c.fetchone()

        if not sender or not receiver:
            self._send_json({"error": "Eines der Wallets existiert nicht"}, 404)
            conn.close()
            return

        if sender[0] < amount:
            self._send_json({"error": "Unzureichendes Guthaben"}, 400)
            conn.close()
            return

        # Transaktion durchführen
        new_sender_balance = sender[0] - amount
        new_receiver_balance = receiver[0] + amount
        now = datetime.now().isoformat()

        c.execute("UPDATE wallets SET balance = ? WHERE name = ?", (new_sender_balance, from_wallet))
        c.execute("UPDATE wallets SET balance = ? WHERE name = ?", (new_receiver_balance, to_wallet))
        c.execute("INSERT INTO transactions (from_wallet, to_wallet, amount, timestamp) VALUES (?, ?, ?, ?)",
                  (from_wallet, to_wallet, amount, now))
        conn.commit()
        conn.close()

        self._send_json({
            "message": "Transaktion erfolgreich",
            "from": from_wallet,
            "to": to_wallet,
            "amount": amount,
            "timestamp": now
        }, 201)

    # --- Routing ---
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        if path == "/api/wallets":
            self.handle_get_wallets()
        elif path == "/api/transactions":
            self.handle_get_transactions(query)
        elif path == "/" or path == "/index.html":
            self._serve_file("static/index.html", "text/html")
        elif path == "/admin.html":
            self._serve_file("static/admin.html", "text/html")
        elif path == "/user.html":
            self._serve_file("static/user.html", "text/html")
        elif path == "/qrious.min.js":
            self._serve_file("static/qrious.min.js", "application/javascript")
        else:
            self._send_json({"error": "Not found"}, 404)

    def _serve_file(self, filename, content_type):
        if not os.path.exists(filename):
            self._send_json({"error": "Datei nicht gefunden"}, 404)
            return
        with open(filename, "rb") as f:
            content = f.read()
        self._set_headers(200, content_type)
        self.wfile.write(content)

    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        data = self._read_json()

        if path == "/api/wallet":
            self.handle_create_wallet(data)
        elif path == "/api/transaction":
            self.handle_create_transaction(data)
        else:
            self._send_json({"error": "Not found"}, 404)


# === Start ===
if __name__ == "__main__":
    init_db()
    import os

    PORT = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", PORT), WalletHandler)

    print("\n=== Demo Bitcoin Wallet Server ===")
    print(" - Lokal:    http://localhost:8000")
    # print(f" - Netzwerk: http://{os.popen('ipconfig getifaddr en0').read().strip()}:8000")
    print("==================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer beendet.")
