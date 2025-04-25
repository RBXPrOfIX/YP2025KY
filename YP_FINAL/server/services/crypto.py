import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Ожидается, что в ENV установлена переменная ENC_KEY_B64: base64.urlsafe_b64encode(os.urandom(32)).decode()
_key_b64 = os.getenv("ENC_KEY_B64")
if not _key_b64:
    raise RuntimeError("Не задана переменная окружения ENC_KEY_B64")
KEY = base64.urlsafe_b64decode(_key_b64)
aesgcm = AESGCM(KEY)

def encrypt_payload(plaintext: bytes) -> str:
    """
    Шифрует payload AES-GCM.
    Возвращает URL-safe base64(iv || ciphertext || tag).
    """
    iv = os.urandom(12)
    ciphertext = aesgcm.encrypt(iv, plaintext, associated_data=None)
    return base64.urlsafe_b64encode(iv + ciphertext).decode()

def decrypt_payload(token_b64: str) -> bytes:
    """
    Дешифрует строку URL-safe base64(iv || ciphertext || tag).
    Возвращает исходные байты.
    """
    data = base64.urlsafe_b64decode(token_b64)
    iv, ct = data[:12], data[12:]
    return aesgcm.decrypt(iv, ct, associated_data=None)