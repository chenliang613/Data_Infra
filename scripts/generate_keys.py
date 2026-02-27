#!/usr/bin/env python3
"""Generate RSA key pairs for demo parties."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dataspace.core.crypto import save_key_pair

KEYS_DIR = Path(__file__).parent.parent / "data" / "keys"

def main():
    parties = [
        ("provider_corp", "数据提供方 (Party A)"),
        ("requester_inc", "数据请求方 (Party B)"),
    ]
    for party_id, name in parties:
        priv, pub = save_key_pair(party_id, KEYS_DIR)
        print(f"✅ 生成密钥对: {name} ({party_id})")
        print(f"   私钥: {KEYS_DIR}/{party_id}.pem")
        print(f"   公钥: {KEYS_DIR}/{party_id}.pub")

if __name__ == "__main__":
    main()
