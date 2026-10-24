"""Flip one input bit and count how many output bits change."""
import argparse
import hashlib
from pathlib import Path

from web3 import Web3

from labkit import title


def flip_first_bit(data: bytes) -> bytes:
    changed = bytearray(data)
    changed[0] ^= 1
    return bytes(changed)


def bits_changed(a: bytes, b: bytes) -> int:
    return sum(bin(x ^ y).count("1") for x, y in zip(a, b))


def report(original: bytes) -> None:
    modified = flip_first_bit(original)
    print(f"input bits changed  1 of {len(original) * 8}")
    for name, fn in (("SHA-256", lambda d: hashlib.sha256(d).digest()), ("Keccak-256", lambda d: bytes(Web3.keccak(d)))):
        d1, d2 = fn(original), fn(modified)
        changed = bits_changed(d1, d2)
        print(f"{name:<11} {changed} of {len(d1) * 8} bits changed ({changed / (len(d1) * 8) * 100:.2f}%)")
        print(f"  original  0x{d1.hex()}")
        print(f"  modified  0x{d2.hex()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Show the avalanche effect.")
    parser.add_argument("--step", choices=["text", "file"], default="text")
    parser.add_argument("--text", default="Fundamentals of Blockchain Technology Development")
    parser.add_argument("--file")
    args = parser.parse_args()
    if args.step == "text":
        title(f"Avalanche effect on text {args.text!r}")
        report(args.text.encode())
    else:
        if not args.file:
            raise SystemExit("--step file needs --file <path>")
        title(f"Avalanche effect on file {args.file}")
        report(Path(args.file).read_bytes())


if __name__ == "__main__":
    main()