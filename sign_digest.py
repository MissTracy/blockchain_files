"""Make a throwaway key, sign the document digest from Lab 1, verify it, and break it. Test keys only."""
import argparse
import hashlib
import json
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys import keys
from web3 import Web3

from labkit import HERE, title

KEY_FILE = HERE / "lab2-throwaway.key"
SIG_FILE = HERE / "lab2-signature.json"
DOC = HERE / "sample-document.txt"
PREFIX = b"\x19Ethereum Signed Message:\n32"  # ERC-191 prefix for a 32-byte message


def sha256_digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def prefixed_hash(digest: bytes) -> bytes:
    """The value ECDSA signs: Keccak-256 of the prefix and the digest."""
    return bytes(Web3.keccak(PREFIX + digest))


def load_account():
    if not KEY_FILE.exists():
        raise SystemExit("No key yet. Run: python sign_digest.py --step keygen")
    return Account.from_key(KEY_FILE.read_text().strip())


def step_keygen() -> None:
    title("New key pair")
    acct = Account.create()
    KEY_FILE.write_text("0x" + bytes(acct.key).hex())
    public = keys.PrivateKey(bytes(acct.key)).public_key.to_bytes()
    by_hand = Web3.to_checksum_address(bytes(Web3.keccak(public))[-20:])
    print(f"private key  32 bytes, saved to {KEY_FILE.name} (not printed)")
    print(f"public key   {len(public)} bytes, 0x{public.hex()[:32]}...{public.hex()[-8:]}")
    print(f"address      {acct.address}")
    print(f"by hand      {by_hand}  (last 20 bytes of Keccak-256 of the public key)")
    print(f"same address: {by_hand == acct.address}")


def step_sign() -> None:
    title("Sign the document digest")
    acct = load_account()
    digest = sha256_digest(DOC.read_bytes())
    trusted = HERE / "trusted-hash.json"
    if trusted.exists():
        print(f"matches Lab 1's trusted hash: {json.loads(trusted.read_text())['sha256'] == digest.hex()}")
    signed = acct.sign_message(encode_defunct(primitive=digest))
    assert bytes(signed.message_hash) == prefixed_hash(digest)
    public = keys.PrivateKey(bytes(acct.key)).public_key.to_bytes()
    SIG_FILE.write_text(json.dumps({
        "signer": acct.address, "public_key": public.hex(), "digest": digest.hex(),
        "r": hex(signed.r), "s": hex(signed.s), "v": signed.v, "signature": bytes(signed.signature).hex(),
    }, indent=2))
    print(f"document  {DOC.name}")
    print(f"digest    0x{digest.hex()}")
    print(f"signer    {acct.address}")
    print(f"r         {hex(signed.r)[:18]}...")
    print(f"s         {hex(signed.s)[:18]}...")
    print(f"v         {signed.v}")
    print(f"saved     {SIG_FILE.name} (signature is {len(bytes(signed.signature))} bytes)")


def check_file(path: Path) -> bool:
    record = json.loads(SIG_FILE.read_text())
    digest = sha256_digest(path.read_bytes())
    recovered = Account.recover_message(encode_defunct(primitive=digest), signature=bytes.fromhex(record["signature"]))
    signature = keys.Signature(vrs=(record["v"] - 27, int(record["r"], 16), int(record["s"], 16)))
    ecdsa_ok = keys.PublicKey(bytes.fromhex(record["public_key"])).verify_msg_hash(prefixed_hash(digest), signature)
    print(f"file            {path.name}")
    print(f"digest          0x{digest.hex()}")
    print(f"claimed signer  {record['signer']}")
    print(f"A. recovered    {recovered}  matches claimed signer: {recovered == record['signer']}")
    print(f"B. public-key ECDSA check: {ecdsa_ok}")
    return recovered == record["signer"] and ecdsa_ok


def step_verify(file: str) -> None:
    title("Verify the signature")
    print("result  " + ("VALID" if check_file(Path(file)) else "INVALID"))


def step_tamper() -> None:
    title("Verify the signature against a changed document")
    tampered = HERE / "sample-document-tampered.txt"
    text = DOC.read_text()
    tampered.write_text(text.replace("4,250.00 ZAR", "42,500.00 ZAR"))
    print("result  " + ("VALID" if check_file(tampered) else "INVALID"))


def step_repeat() -> None:
    title("Sign the same digest twice, then a different one")
    acct = load_account()
    d1 = sha256_digest(DOC.read_bytes())
    d2 = sha256_digest(DOC.read_bytes() + b" ")
    a = acct.sign_message(encode_defunct(primitive=d1))
    b = acct.sign_message(encode_defunct(primitive=d1))
    c = acct.sign_message(encode_defunct(primitive=d2))
    print(f"same digest, signing 1  r = {hex(a.r)[:22]}...")
    print(f"same digest, signing 2  r = {hex(b.r)[:22]}...")
    print(f"different digest        r = {hex(c.r)[:22]}...")
    print(f"signings 1 and 2 identical: {a.signature == b.signature}")
    print(f"signing 3 has the same r as signing 1: {c.r == a.r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sign and verify the Lab 1 digest.")
    parser.add_argument("--step", choices=["keygen", "sign", "verify", "tamper", "repeat"], required=True)
    parser.add_argument("--file", default=str(DOC))
    args = parser.parse_args()
    if args.step == "verify":
        step_verify(args.file)
    else:
        {"keygen": step_keygen, "sign": step_sign, "tamper": step_tamper, "repeat": step_repeat}[args.step]()


if __name__ == "__main__":
    main()
