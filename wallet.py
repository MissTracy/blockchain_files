"""Lab 3: mnemonic, HD accounts, encrypted keystore, and an offline-signed registration. Throwaway keys only."""
import argparse
import getpass
import hashlib
import json
import os
import time

from eth_account import Account
from mnemonic import Mnemonic
from web3 import Web3

from labkit import HERE, connect, registry, title

MNEMONIC_FILE = HERE / "lab3-throwaway.mnemonic"
KEYSTORE_FILE = HERE / "lab3-keystore.json"
DOC = HERE / "sample-document.txt"
PATH = "m/44'/60'/0'/0/"  # BIP-44 Ethereum path; the account index is added at the end
ANVIL_TEST_MNEMONIC ="test test test test test test test test test test test junk"  # public, for the cross-check only

# Published BIP-39 sample values: entropy, passphrase, expected mnemonic, expected seed
KNOWN_VECTORS = [
    ("Vector 1", "0c1e24e5917779d297e14d45f14e1a1a", "",
     "army van defense carry jealous true garbage claim echo media make crunch",
     "5b56c417303faa3fcba7e57400e120a0ca83ec5a4fc9ffba757fbe63fbd77a89a1a3be4c67196f57c39a88b76373733891bfaba16ed27a813ceed498804c0570"),
    ("Vector 2", "0c1e24e5917779d297e14d45f14e1a1a", "SuperDuperSecret",
     "army van defense carry jealous true garbage claim echo media make crunch",
     "3b5df16df2157104cfdd22830162a5e170c0161653e3afe6c88defeefb0818c793dbb28ab3ab091897d0715861dc8a18358f80b79d49acf64142ae57037d1d54"),
    ("Vector 3", "2041546864449caff939d32d574753fe684d3c947c3346713dd8423e74abcf8c", "",
     "cake apple borrow silk endorse fitness top denial coil riot stay wolf luggage oxygen faint major edit measure invite love trap field dilemma oblige",
     "3269bce2674acbd188d4f120072b13b088a0ecf87c6e4cae41657a0bb78f5315b33b3a04356e53d062e55f1e0deaa082df8d487381379df848a6ad7e98798404"),
]


def enable_hd() -> None:
    # eth-account labels its HD features unaudited; acceptable here because the keys are throwaway
    Account.enable_unaudited_hdwallet_features()


def mnemonic_by_hand(entropy: bytes, wordlist: list) -> str:
    """BIP-39: entropy plus the first len/32 bits of its SHA-256, cut into 11-bit word indexes."""
    bits = bin(int.from_bytes(entropy, "big"))[2:].zfill(len(entropy) * 8)
    checksum = bin(int.from_bytes(hashlib.sha256(entropy).digest(), "big"))[2:].zfill(256)[:len(entropy) * 8 // 32]
    allbits = bits + checksum
    return " ".join(wordlist[int(allbits[i:i + 11], 2)] for i in range(0, len(allbits), 11))


def load_mnemonic() -> str:
    if not MNEMONIC_FILE.exists():
        raise SystemExit("No mnemonic yet. Run: python wallet.py --step mnemonic")
    return MNEMONIC_FILE.read_text().strip()


def step_mnemonic() -> None:
    title("Published BIP-39 test vectors")
    m = Mnemonic("english")
    for label, entropy_hex, passphrase, words, seed_hex in KNOWN_VECTORS:
        entropy = bytes.fromhex(entropy_hex)
        words_ok = m.to_mnemonic(entropy) == words and mnemonic_by_hand(entropy, m.wordlist) == words
        seed_ok = m.to_seed(words, passphrase).hex() == seed_hex
        print(f"{label}  {len(words.split())} words  words {'MATCH' if words_ok else 'DIFFERENT'}  seed {'MATCH' if seed_ok else 'DIFFERENT'}")
    title("Generated test mnemonic")
    phrase = m.generate(128)
    MNEMONIC_FILE.write_text(phrase)
    print(phrase)
    print(f"checksum valid: {m.check(phrase)}")
    print(f"saved to {MNEMONIC_FILE.name}")


def step_derive() -> None:
    enable_hd()
    title("Derived accounts, path m/44'/60'/0'/0/i")
    phrase = load_mnemonic()
    for i in range(3):
        print(f"{i}  {Account.from_mnemonic(phrase, account_path=PATH + str(i)).address}")
    title("Cross-check against Anvil's public test mnemonic")
    anvil = connect().eth.accounts
    for i in range(3):
        mine = Account.from_mnemonic(ANVIL_TEST_MNEMONIC, account_path=PATH + str(i)).address
        print(f"{i}  {mine}  Anvil {anvil[i]}  {'MATCH' if mine == anvil[i] else 'DIFFERENT'}")


def step_keystore() -> None:
    enable_hd()
    title("Encrypt the first account's key")
    acct = Account.from_mnemonic(load_mnemonic())
    passphrase = os.environ.get("LAB3_PASSPHRASE") or getpass.getpass("Choose a passphrase (hidden): ")
    t0 = time.perf_counter()
    keystore = Account.encrypt(acct.key, passphrase)
    seconds = time.perf_counter() - t0
    KEYSTORE_FILE.write_text(json.dumps(keystore))
    crypto = keystore["crypto"]
    params = crypto["kdfparams"]
    print(f"keystore version  {keystore['version']}")
    print(f"address           {keystore['address']}")
    print(f"cipher            {crypto['cipher']}")
    print(f"key derivation    {crypto['kdf']}  n={params['n']} r={params['r']} p={params['p']}")
    print(f"encryption time   {seconds:.2f} s")
    title("Open it again")
    stored = json.loads(KEYSTORE_FILE.read_text())
    print(f"right passphrase: key matches the account: {bytes(Account.decrypt(stored, passphrase)) == bytes(acct.key)}")
    try:
        Account.decrypt(stored, passphrase + "x")
        print("wrong passphrase: opened")
    except ValueError as exc:
        print(f"wrong passphrase: refused ({exc})")


def step_register() -> None:
    enable_hd()
    title("Register the Lab 1 document, signed offline")
    w3 = connect()
    contract, _ = registry(w3)
    acct = Account.from_mnemonic(load_mnemonic())
    digest = hashlib.sha256(DOC.read_bytes()).digest()
    print(f"address       {acct.address}")
    if w3.eth.get_balance(acct.address) == 0:
        funder = w3.eth.accounts[0]
        w3.eth.wait_for_transaction_receipt(w3.eth.send_transaction({"from": funder, "to": acct.address, "value": Web3.to_wei(1, "ether")}))
        print(f"funded        1 test ether from Anvil account 0 ({funder})")
    print(f"balance       {Web3.from_wei(w3.eth.get_balance(acct.address), 'ether')} test ether")
    if contract.functions.verify(digest).call()[0] != "0x0000000000000000000000000000000000000000":
        raise SystemExit("This document is already registered on this chain. Restart Anvil from the saved state to repeat.")
    base = w3.eth.fee_history(1, "latest", [50])["baseFeePerGas"][-1]
    tip = Web3.to_wei(1, "gwei")
    tx = contract.functions.register(digest).build_transaction({
        "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address), "chainId": w3.eth.chain_id,
        "maxFeePerGas": base * 2 + tip, "maxPriorityFeePerGas": tip,
    })
    signed = acct.sign_transaction(tx)  # signed on this machine; the node only receives the signed bytes
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    registrant = contract.functions.verify(digest).call()[0]
    recovered = Account.recover_transaction(w3.eth.get_raw_transaction(tx_hash))
    print(f"block         {receipt['blockNumber']}, status {receipt['status']}")
    print(f"registry registrant is the derived account:{registrant == acct.address}")
    print(f"recovered signer is the derived account:{recovered == acct.address}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lab 3 wallet.")
    parser.add_argument("--step", choices=["mnemonic", "derive", "keystore", "register"], required=True)
    step = {"mnemonic": step_mnemonic, "derive": step_derive, "keystore": step_keystore, "register": step_register}
    step[parser.parse_args().step]()


if __name__ == "__main__":
    main()
