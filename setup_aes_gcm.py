
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def generate_credentials():
    print("--- Generador de Credenciales Seguras (AES-GCM) ---")
    
    # 1. Generar Master Key (32 bytes para AES-256)
    key = AESGCM.generate_key(bit_length=256)
    key_b64 = base64.b64encode(key).decode('utf-8')
    print(f"\n[1] NUEVA Master Key (Guardar en DB_ENCRYPTION_KEY):")
    print(f"{key_b64}")
    
    # 2. Encriptar Password
    pwd = input("\nIngrese la contraseña de Base de Datos en texto plano: ").strip()
    if not pwd:
        print("Error: Contraseña vacía.")
        return

    aesgcm = AESGCM(key)
    nonce = os.urandom(12) # 96-bit nonce (Recomendado NIST)
    
    # Encrypt devuelve: ciphertext + auth_tag
    ciphertext_with_tag = aesgcm.encrypt(nonce, pwd.encode('utf-8'), associated_data=None)
    
    # Payload final: Nonce + Ciphertext + Tag
    final_payload = nonce + ciphertext_with_tag
    payload_b64 = base64.b64encode(final_payload).decode('utf-8')
    
    print(f"\n[2] Password Encriptado (Guardar en DB_PASSWORD):")
    print(f"{payload_b64}")
    
    print("\n--- Instrucciones ---")
    print("1. Copie el valor [1] en su archivo .env como DB_ENCRYPTION_KEY")
    print("2. Copie el valor [2] en su archivo .env como DB_PASSWORD")
    print("3. BORRE ESTE SCRIPT o el historial de su terminal después de usarlo.")

if __name__ == "__main__":
    try:
        generate_credentials()
    except Exception as e:
        print(f"Error: {e}")
