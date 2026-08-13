from pathlib import Path

path = Path("merit/compiler.py")
data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
path.write_bytes(data)
