import os
import base64
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Ожидается, что в ENV установлена переменная ENC_KEY_B64
_key_b64 = os.getenv("ENC_KEY_B64")
if not _key_b64:
    raise RuntimeError("Не задана переменная окружения ENC_KEY_B64")
KEY = base64.urlsafe_b64decode(_key_b64)
aesgcm = AESGCM(KEY)

def encrypt_request(payload: dict) -> str:
    """
    Принимает словарь, сериализует в JSON UTF-8 и шифрует AES-GCM.
    Возвращает URL-safe base64(iv || ciphertext || tag).
    """
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    iv = os.urandom(12)
    ciphertext = aesgcm.encrypt(iv, raw, associated_data=None)
    return base64.urlsafe_b64encode(iv + ciphertext).decode()

def decrypt_response(token: str) -> dict:
    """
    Принимает ответ от сервера в виде URL-safe base64(iv || ciphertext || tag),
    возвращает распарсенный JSON.
    """
    data = base64.urlsafe_b64decode(token)
    iv, ct = data[:12], data[12:]
    raw = aesgcm.decrypt(iv, ct, associated_data=None)
    return json.loads(raw.decode("utf-8"))