"""Hash text or a file with SHA-256 and Keccak-256."""
import argparse
import hashlib
from pathlib import Path

from web3 import Web3

from labkit import title

DEFAULT_TEXT = "Fundamentals of Blockchain Technology Development"

# (source, algorithm, input, published digest); sources are for the course team, not shown to learners
KNOWN_VALUES = [
    ("Bashir 2018, p. 195", "sha256", b"Hello", "185f8db32271fe25f561a6fc938b2e264306ec304eda518007d1764826381969"),
    ("Bashir 2018, p. 195", "sha256", b"hello", "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"),
    ("Wong 2021, p. 28", "sha256", b"hella", "70de66401b1399d79b843521ee726dcec1e9a8cb5708ec1520f1f3bb4b1dd984"),
    ("Wong 2021, p. 35", "sha256", b"hello world", "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"),
    ("Antonopoulos and Wood 2019, ch. 4", "keccak256", b"", "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"),
    ("Antonopoulos and Wood 2019, ch. 4", "sha3_256", b"", "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a"),
]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def keccak256_hex(data: bytes) -> str:
    return bytes(Web3.keccak(data)).hex()


def digest(algorithm: str, data: bytes) -> str:
    if algorithm == "sha256":
        return sha256_hex(data)
    if algorithm == "sha3_256":
        return hashlib.sha3_256(data).hexdigest()
    return keccak256_hex(data)


def step_hash(data: bytes, label: str) -> None:
    title(f"Hash of {label}")
    print(f"input length  {len(data)} bytes")
    print(f"SHA-256       0x{sha256_hex(data)}")
    print(f"Keccak-256    0x{keccak256_hex(data)}")


def step_determinism(data: bytes, runs: int) -> None:
    title(f"Same input hashed {runs} times")
    print(f"distinct SHA-256 digests     {len({sha256_hex(data) for _ in range(runs)})}")
    print(f"distinct Keccak-256 digests  {len({keccak256_hex(data) for _ in range(runs)})}")


def step_known_values() -> None:
    title("Published example digests")
    for _source, algorithm, data, published in KNOWN_VALUES:
        name = {"sha256": "SHA-256", "sha3_256": "SHA3-256", "keccak256": "Keccak-256"}[algorithm]
        print(f"{name}({data.decode()!r})".ljust(24) + ("MATCH" if digest(algorithm, data) == published else "DIFFERENT"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Hash text or a file with SHA-256 and Keccak-256.")
    parser.add_argument("--step", choices=["hash", "determinism", "known-values"], default="hash")
    parser.add_argument("--text")
    parser.add_argument("--file")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    if args.step == "known-values":
        return step_known_values()
    if args.file:
        data, label = Path(args.file).read_bytes(), f"file {args.file}"
    else:
        text = DEFAULT_TEXT if args.text is None else args.text
        data, label = text.encode(), f"text {text!r}"
    if args.step == "hash":
        step_hash(data, label)
    else:
        step_determinism(data, args.runs)


if __name__ == "__main__":
    main()
