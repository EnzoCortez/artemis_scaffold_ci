
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
    
    # 2. Encriptar Usuario
    user = input("\nIngrese el USUARIO de Base de Datos en texto plano: ").strip()
    if not user:
        print("Error: Usuario vacío.")
        return

    aesgcm = AESGCM(key)
    
    # Encrypt User
    nonce_user = os.urandom(12) 
    ciphertext_user = aesgcm.encrypt(nonce_user, user.encode('utf-8'), associated_data=None)
    payload_user = base64.b64encode(nonce_user + ciphertext_user).decode('utf-8')

    print(f"\n[2] Usuario Encriptado (Guardar en DB_USER_ENCRYPTED):")
    print(f"{payload_user}")

    # 3. Encriptar Password
    pwd = input("\nIngrese la CONTRASEÑA de Base de Datos en texto plano: ").strip()
    if not pwd:
        print("Error: Contraseña vacía.")
        return

    # Encrypt Password
    nonce_pwd = os.urandom(12)
    ciphertext_pwd = aesgcm.encrypt(nonce_pwd, pwd.encode('utf-8'), associated_data=None)
    payload_pwd = base64.b64encode(nonce_pwd + ciphertext_pwd).decode('utf-8')
    
    print(f"\n[3] Password Encriptado (Guardar en DB_PASSWORD_ENCRYPTED):")
    print(f"{payload_pwd}")
    
    # 4. Generar DJANGO_SECRET_KEY
    import secrets
    secret_key = secrets.token_urlsafe(50)
    print(f"\n[4] DJANGO_SECRET_KEY (Cifrado Criptográfico Estándar):")
    print(f"{secret_key}")

    print("\n--- Instrucciones ---")
    print("1. Copie el valor [1] en su archivo .env como DB_ENCRYPTION_KEY")
    print("2. Copie el valor [2] en su archivo .env como DB_USER_ENCRYPTED")
    print("3. Copie el valor [3] en su archivo .env como DB_PASSWORD_ENCRYPTED")
    print("4. Copie el valor [4] en su archivo .env como DJANGO_SECRET_KEY")
    print("3. BORRE ESTE SCRIPT o el historial de su terminal después de usarlo.")

if __name__ == "__main__":
    try:
        generate_credentials()
    except Exception as e:
        print(f"Error: {e}")
