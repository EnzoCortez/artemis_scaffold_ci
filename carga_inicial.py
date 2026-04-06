import os
import django
import sys
from pathlib import Path

# Configurar entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artemis_project.settings')
django.setup()

from ioc_manager.models import IocEntry, Tool, IocTool
from ioc_manager.utils import detect_ioc_type

def main():
    print("="*60)
    print("   SCRIPT DE CARGA INICIAL POR HERRAMIENTA (ARTEMIS)")
    print("="*60)
    print("INSTRUCCIONES:")
    print("Coloca tus archivos .txt nombrados EXACTAMENTE como la")
    print("herramienta destino en la base de datos.")
    print("Ejemplo: 'EDR (Crowdstrike).txt', 'Waf.txt', 'IPS.txt'")
    print("Ubicación: Crea una carpeta llamada 'cargas_iniciales' al")
    print("lado de este script y pon ahí los archivos.")
    print("="*60)

    base_dir = Path(__file__).resolve().parent
    cargas_dir = base_dir / 'cargas_iniciales'

    if not cargas_dir.exists():
        cargas_dir.mkdir()
        print(f"[!] Se creó la carpeta '{cargas_dir}'.")
        print("Por favor, pon tus archivos TXT allí y vuelve a ejecutar este script.")
        return

    txt_files = list(cargas_dir.glob("*.txt"))
    if not txt_files:
        print("[!] No se encontraron archivos .txt en 'cargas_iniciales/'.")
        return

    for txt_path in txt_files:
        tool_name = txt_path.stem  # Nombre del archivo sin .txt
        print(f"\n---> Procesando archivo: {txt_path.name}")
        
        # Buscar herramienta exacta o parcial
        tool = Tool.objects.filter(name__iexact=tool_name).first()
        if not tool:
            tool = Tool.objects.filter(name__icontains=tool_name).first()
            
        if not tool:
            print(f"[ERROR] No existe una herramienta llamada '{tool_name}' en la BD. Saltando archivo.")
            continue
            
        print(f"[*] Destino confirmado: {tool.name}")
        
        # Leer archivo
        with open(txt_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        
        if not lines:
            print("[*] Archivo vacío. Saltando.")
            continue

        print(f"[*] Analizando {len(lines)} líneas de texto...")
        
        to_create = []
        valid_iocs = set()
        invalid_lines = []

        # Limpiar y detectar
        for value in set(lines): # Set remueve duplicados del mismo txt
            tipo = detect_ioc_type(value)
            if not tipo:
                invalid_lines.append(value)
                continue
            valid_iocs.add((value, tipo))

        if invalid_lines:
            print(f"[!] Se omitieron {len(invalid_lines)} líneas no válidas (No son IP, Dominio, URL ni Hash).")

        # Ingestar
        # 1. Obtener los que ya existen en la base de datos globales para no crear IocEntry duplicados
        from ioc_manager.models import IocType
        ioc_type_map = {t.name.lower(): t for t in IocType.objects.all()}
        
        values_only = [v[0] for v in valid_iocs]
        existing_iocs_db = IocEntry.objects.filter(value__in=values_only)
        existing_map = {ioc.value.lower(): ioc for ioc in existing_iocs_db}

        new_iocs_to_create = []
        for val, tipo_str in valid_iocs:
            val_lower = val.lower()
            if val_lower not in existing_map:
                tipo_obj = ioc_type_map.get(tipo_str.lower())
                if tipo_obj:
                    # Crear nuevo IoC asociado temporalmente a Nobody o un Batch fantasma
                    new_iocs_to_create.append(IocEntry(
                        value=val,
                        ioc_type=tipo_obj,
                        # Para cargas iniciales, no hay 'created_by' mapeado (así que admin si no es null)
                        created_by_id=1  # Idealmente el ID del admin, si da error revisar modelo
                    ))

        # Bulk Create a la DB
        if new_iocs_to_create:
            print(f"[*] Insertando {len(new_iocs_to_create)} IoCs NUEVOS en la DB maestra...")
            try:
                # bulk_create ignora conflictos si los IDs no existen
                created = IocEntry.objects.bulk_create(new_iocs_to_create, ignore_conflicts=True)
            except Exception as e:
                print(f"[ERROR DB] Al insertar nuevos IoC: {e}")
                
        # Ahora recuperar todos por valor
        final_db_iocs = IocEntry.objects.filter(value__in=values_only)
        
        # 2. Asociar a la herramienta ignorando las Reglas (ToolIndicatorRule)
        # Buscar qué enlaces ya existen entre estos IoC y ESTA herramienta
        existing_links = IocTool.objects.filter(ioc__in=final_db_iocs, tool=tool).values_list('ioc_id', flat=True)
        existing_links_set = set(existing_links)
        
        links_to_create = []
        for ioc in final_db_iocs:
            if ioc.id not in existing_links_set:
                links_to_create.append(IocTool(
                    ioc=ioc,
                    tool=tool,
                    # action='Añadido por carga inicial',
                    # ingested_at=timezone.now() => automatico del modelo
                ))
        
        if links_to_create:
            print(f"[*] Vinculando {len(links_to_create)} IoCs forzosamente a la herramienta {tool.name}...")
            IocTool.objects.bulk_create(links_to_create, ignore_conflicts=True)
            print(f"[EXITO] {tool.name} ahora tiene sus indicadores blindados.")
        else:
            print(f"[*] Todos los indicadores válidos del txt ya estaban vinculados a {tool.name}.")

if __name__ == '__main__':
    main()
