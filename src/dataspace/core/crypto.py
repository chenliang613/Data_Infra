"""RSA cryptographic utilities: key generation, signing, verification."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.exceptions import InvalidSignature

from .exceptions import SignatureError


def generate_key_pair() -> tuple[RSAPrivateKey, RSAPublicKey]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key, private_key.public_key()


def private_key_to_pem(key: RSAPrivateKey) -> str:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def public_key_to_pem(key: RSAPublicKey) -> str:
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def load_private_key(pem: str) -> RSAPrivateKey:
    return serialization.load_pem_private_key(pem.encode(), password=None)


def load_public_key(pem: str) -> RSAPublicKey:
    return serialization.load_pem_public_key(pem.encode())


def sign(data: bytes, private_key: RSAPrivateKey) -> str:
    """Sign data, return base64-encoded signature."""
    signature = private_key.sign(
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()


def verify(data: bytes, signature_b64: str, public_key: RSAPublicKey) -> bool:
    """Verify signature; raises SignatureError on failure."""
    try:
        public_key.verify(
            base64.b64decode(signature_b64),
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except (InvalidSignature, Exception) as exc:
        raise SignatureError(f"Signature verification failed: {exc}") from exc


def save_key_pair(party_id: str, keys_dir: str | Path) -> tuple[str, str]:
    """Generate and persist key pair for a party. Returns (private_pem, public_pem)."""
    keys_path = Path(keys_dir)
    keys_path.mkdir(parents=True, exist_ok=True)
    private_key, public_key = generate_key_pair()
    priv_pem = private_key_to_pem(private_key)
    pub_pem = public_key_to_pem(public_key)
    (keys_path / f"{party_id}.pem").write_text(priv_pem)
    (keys_path / f"{party_id}.pub").write_text(pub_pem)
    return priv_pem, pub_pem


def load_key_pair(party_id: str, keys_dir: str | Path) -> tuple[str, str]:
    """Load existing key pair. Returns (private_pem, public_pem)."""
    keys_path = Path(keys_dir)
    priv_pem = (keys_path / f"{party_id}.pem").read_text()
    pub_pem = (keys_path / f"{party_id}.pub").read_text()
    return priv_pem, pub_pem


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
