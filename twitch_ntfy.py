import os
import re
import socket
import sys
import time
import requests
from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, "env"))

TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL", "").lower()
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh")
NTFY_TOKEN = os.getenv("NTFY_TOKEN", "")
SHOW_BADGES = os.getenv("SHOW_BADGES", "false").lower() in ("true", "1", "yes")

TWITCH_HOST = "irc.chat.twitch.tv"
TWITCH_PORT = 6667
RECONNECT_DELAY = 5


def send_ntfy(message: str) -> None:
    url = f"{NTFY_SERVER}/{NTFY_TOPIC}"
    headers = {}
    if NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {NTFY_TOKEN}"
    try:
        resp = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ntfy error] {e}")


def parse_privmsg(line: str) -> tuple[str, str, str] | None:
    if " PRIVMSG #" not in line:
        return None
    match = re.search(r":(\S+)!.* PRIVMSG #\S+ :(.*)", line)
    if not match:
        return None
    nick = match.group(1)
    msg = match.group(2)
    badge_match = re.search(r"badges=([^;]*)", line)
    badges = ""
    if badge_match and badge_match.group(1):
        badges = ", ".join(b.split("/")[0] for b in badge_match.group(1).split(","))
    return nick, msg, badges


def connect() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(300)
    sock.connect((TWITCH_HOST, TWITCH_PORT))
    sock.send(f"PASS oauth:alphanumeric-only\r\n".encode("utf-8"))
    sock.send(f"NICK justinfan12345\r\n".encode("utf-8"))
    if SHOW_BADGES:
        sock.send(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
    sock.send(f"JOIN #{TWITCH_CHANNEL}\r\n".encode("utf-8"))
    return sock


def main() -> None:
    if not TWITCH_CHANNEL or not NTFY_TOPIC:
        raise SystemExit("TWITCH_CHANNEL and NTFY_TOPIC must be set in .env")

    print(f"Connecting to #{TWITCH_CHANNEL}...")
    sock = connect()
    buf = ""

    try:
        while True:
            try:
                data = sock.recv(4096).decode("utf-8", errors="replace")
            except socket.timeout:
                continue

            if not data:
                print("Connection closed, reconnecting...")
                time.sleep(RECONNECT_DELAY)
                sock = connect()
                buf = ""
                continue

            buf += data
            while "\r\n" in buf:
                line, buf = buf.split("\r\n", 1)

                if line.startswith("PING"):
                    sock.send(b"PONG :tmi.twitch.tv\r\n")
                    continue

                parsed = parse_privmsg(line)
                if parsed:
                    try:
                        nick, msg, badges = parsed
                        if SHOW_BADGES and badges:
                            text = f"[{badges}] {nick}: {msg}"
                        else:
                            text = f"{nick}: {msg}"
                        print(text)
                        send_ntfy(text)
                    except Exception as e:
                        print(f"[error] {e}: {line[:200]}")

    except KeyboardInterrupt:
        print("\nDisconnected.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
