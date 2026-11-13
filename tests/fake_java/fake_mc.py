"""A tiny stand-in for a Minecraft server: prints log lines, obeys a few commands."""
import sys, time

def say(msg):
    print(f"[{time.strftime('%H:%M:%S')} INFO]: {msg}", flush=True)

say("Starting minecraft server version 1.21.4")
time.sleep(0.3)
say('Done (0.31s)! For help, type "help"')
for line in sys.stdin:
    cmd = line.strip()
    if cmd == "stop":
        say("Stopping server")
        sys.exit(0)
    elif cmd == "crash":
        sys.exit(1)
    elif cmd.startswith("join "):
        say(f"{cmd[5:]} joined the game")
    elif cmd.startswith("leave "):
        say(f"{cmd[6:]} left the game")
    else:
        say(f"Unknown or incomplete command: {cmd}")
