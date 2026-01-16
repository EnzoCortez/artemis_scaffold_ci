
import pyodbc
import sys

# Lista de posibles direcciones del servidor para probar
SERVERS_TO_TRY = [
    '192.100.128.16',  # REEMPLAZAR con la IP de tu maquina FISICA
    'host.docker.internal,51239',
    'ENZO\\SQLEXPRESS',
]

DATABASE = 'artemis_db'
USERNAME = 'artemis_user'
PASSWORD = 'PasswordSegura123!'
DRIVER = '{ODBC Driver 17 for SQL Server}'

print("--- DIAGNOSTICO DE CONEXION SQL SERVER ---")
print(f"Driver: {DRIVER}")
print(f"Usuario: {USERNAME}")

success = False

for server in SERVERS_TO_TRY:
    print(f"\n[INTENTO] Conectando a: {server} ...")
    conn_str = f'DRIVER={DRIVER};SERVER={server};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;'
    
    try:
        conn = pyodbc.connect(conn_str, timeout=3)
        print(f"!! EXITO !! Se conecto usando: {server}")
        conn.close()
        success = True
        break
    except Exception as e:
        print(f"XX Fallo. Error parcial: {str(e)[:100]}...")

if not success:
    print("\n\n!!! TODAS LAS CONEXIONES FALLARON !!!")
    print("El servicio esta corriendo (vimos tu captura), asi que el problema es PROTOCOLO o PUERTO.")
    print("POR FAVOR REALIZA ESTO:")
    print("1. En SQL Config Manager, ve a la izquierda: 'SQL Server Network Configuration' > 'Protocols for SQLEXPRESS'.")
    print("2. A la derecha, veras 'TCP/IP'. Debe decir 'Enabled'. Si dice 'Disabled', cambialo.")
    print("3. Dale doble clic a 'TCP/IP', ve a la pestana 'IP Addresses'.")
    print("4. Baja hasta el final, en 'IPAll'. Asegurate que 'TCP Dynamic Ports' NO este en 0 (borralo si quieres puerto fijo) o que 'TCP Port' sea 1433.")
    print("5. IMPORTANTE: Reinicia el servicio 'SQL Server (SQLEXPRESS)' tras cualquier cambio.")
else:
    print("\n!! SOLUCION ENCONTRADA:")
    print("Modifica tu archivo settings.py y pon en 'HOST' el valor que funciono arriba.")
