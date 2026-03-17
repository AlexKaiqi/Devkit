"""一次性脚本：生成 VAPID 密钥对，保存到 implementation/data/vapid_keys.json

private_key 存储格式：EC P-256 私钥的 raw 32字节，base64url 编码（无 padding）
public_key_b64 存储格式：未压缩公钥点 65字节，base64url 编码（无 padding）
"""

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

# 生成 EC P-256 密钥对
private_key = ec.generate_private_key(ec.SECP256R1())
public_key = private_key.public_key()

# 私钥 raw 32 字节 → base64url（pywebpush Vapid.from_string 期望的格式）
priv_raw = private_key.private_numbers().private_value.to_bytes(32, "big")
priv_b64 = base64.urlsafe_b64encode(priv_raw).rstrip(b"=").decode()

# 公钥 uncompressed point 65 字节 → base64url
pub_raw = public_key.public_bytes(encoding=Encoding.X962, format=PublicFormat.UncompressedPoint)
pub_b64 = base64.urlsafe_b64encode(pub_raw).rstrip(b"=").decode()

out = Path(__file__).resolve().parents[2] / "data" / "vapid_keys.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(
    json.dumps({"private_key": priv_b64, "public_key_b64": pub_b64}, indent=2),
    encoding="utf-8",
)
print(f"VAPID keys saved to {out}")
print(f"Public key (b64url): {pub_b64}")
