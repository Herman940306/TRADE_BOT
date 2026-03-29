import hashlib
import hmac

payload = b'{"signal_id": "TEST-PHASE1-001", "symbol": "BTCZAR", "side": "BUY", "price": "1250000.50", "quantity": "0.001"}'
secret = "dev_secret_key_32_characters_minimum_1234"
sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
