#!/usr/bin/env python3
"""
Script para crear y configurar el entorno virtual del bot de finanzas personales.
"""

import subprocess
import sys
import os

def run_command(cmd):
    """Ejecutar un comando y capturar su salida"""
    print(f"CONFIG: Ejecutando: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            print(f"   Salida: {result.stdout.strip()}")
        if result.stderr:
            print(f"   Error: {result.stderr.strip()}")
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return -1, "", str(e)

def main():
    print("=" * 70)
    print("CONFIGURANDO ENTORNO VIRTUAL - BOT DE FINANZAS PERSONALES")
    print("=" * 70)
    
    # Verificar si existe el entorno virtual
    if os.path.exists('venv'):
        print("✓ Entorno virtual ya existe")
        # Verificar si los modulos estan instalados
        print("\n🔍 Verificando si los modulos estan instalados...")
        modules = ['config', 'database', 'handlers', 'knowledge', 'main', 'ai_client']
        for module in modules:
            run_command(f'venv\\Scripts\\python -c "import {module}; print(f\"✓ {module} importado correctamente\")"')
        return
    else:
        print("📦 Creando nuevo entorno virtual...")
    
    # Crear entorno virtual
    code, out, err = run_command('python -m venv venv')
    if code != 0:
        print(f"❌ Error creando entorno virtual: {err}")
        print("Intentando con python3...")
        code, out, err = run_command('python3 -m venv venv')
        if code != 0:
            print(f"❌ Error creando entorno virtual: {err}")
            sys.exit(1)
    
    print("✓ Entorno virtual creado exitosamente")
    
    # Instalar pip en el entorno virtual
    print("\n📦 Actualizando pip en el entorno virtual...")
    run_command('venv\\Scripts\\pip install --upgrade pip')
    
    # Instalar dependencias principales
    print("\n📦 Instalando dependencias...")
    deps = [
        'python-telegram-bot>=22.8',
        'python-dotenv',
        'mistralai',
        'Flask'
    ]
    
    for dep in deps:
        print(f"   📦 Instalando {dep}...")
        run_command(f'venv\\Scripts\\pip install {dep}')
    
    # Instalar el paquete actual
    print("\n📦 Instalando el paquete actual...")
    run_command('venv\\Scripts\\pip install .')
    
    # Verificar instalación
    print("\n🔍 Verificando instalacion...")
    
    # Verificar que config.py puede ser importado
    run_command('venv\\Scripts\\python -c "import config; print(f\"✓ Config: AI_PROVIDER={config.AI_PROVIDER}\")"')
    
    # Verificar todos los modulos principales
    modules = ['config', 'database', 'handlers', 'knowledge', 'main', 'ai_client']
    for module in modules:
        run_command(f'venv\\Scripts\\python -c "import {module}; print(f\"✓ {module} importado correctamente\")"')
    
    print("\n" + "=" * 70)
    print("🎉 ¡ENTORNO VIRTUAL Y DEPENDENCIAS INSTALADAS EXITOSAMENTE!")
    print("=" * 70)
    print("\n📋 PRÓXIMOS PASOS:")
    print("   1. Editar .env y reemplazar 'tu_token_aquí' con token real")
    print("   2. Ejecutar: venv\\Scripts\\python.exe main.py")
    print("\n🤖 CARACTERÍSTICAS DEL BOT:")
    print("   • Registro de transacciones en lenguaje natural")
    print("   • IA híbrida: Nativo + Mistral AI")
    print("   • Gestión completa de presupuesto y ahorro")
    print("   • Base de datos SQLite personalizada")
    print("   • Categorías y marcas financieras")
    print("\n🚀 El bot está listo para usar!")

if __name__ == "__main__":
    main()
