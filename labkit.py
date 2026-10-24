"""Helpers shared by the module 3 lab scripts."""
import json
from pathlib import Path

from web3 import Web3

HERE = Path(__file__).parent
ANVIL_URL = "http://127.0.0.1:8545"


def title(text: str) -> None:
    print(f"\n== {text} ==")


def connect() -> Web3:
    w3 = Web3(Web3.HTTPProvider(ANVIL_URL))
    if not w3.is_connected():
        raise SystemExit(f"Anvil is not running at {ANVIL_URL}. Start it as the lesson describes.")
    return w3


def registry(w3: Web3):
    """Return the M2 DocumentRegistry contract and its address file contents."""
    files = [HERE / "seed-data" / "contract-address.json", HERE / "out" / "DocumentRegistry.sol" / "DocumentRegistry.json"]
    missing = [str(f.relative_to(HERE)) for f in files if not f.exists()]
    if missing:
        raise SystemExit(f"Not found: {', '.join(missing)}. Run this from the registry folder.")
    info = json.loads(files[0].read_text())
    abi = json.loads(files[1].read_text())["abi"]
    return w3.eth.contract(address=Web3.to_checksum_address(info["address"]), abi=abi), info
