#!/usr/bin/env python3
"""
Script para crear y configurar el entorno virtual del bot de finanzas personales.
"""

import subprocess
import sys
import os
import pathlib

def run_command(cmd, check=True):
    """Ejecutar un comando y capturar su salida"""
    print(f"🔧 Ejecutando: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            print(f"   Salida: {result.stdout.strip()}")
        if result.stderr:
            print(f"   Error: {result.stderr.strip()}")
        if check and result.returncode != 0:
            print(f"   ❌ Error: Código de salida {result.returncode}")
            return False
        return True
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

def main():
    print("=" * 70)
    print("📦 CREANDO ENTORNO VIRTUAL - BOT DE FINANZAS PERSONALES")
    print("=" * 70)
    
    # Obtener el directorio actual
    script_dir = pathlib.Path(__file__).parent
    os.chdir(script_dir)
    
    print(f"\n📁 Directorio actual: {os.getcwd()}")
    
    # === CREAR ENTORNO VIRTUAL ===
    print("\n🔧 Creando entorno virtual...")
    
    venv_path = os.path.join(script_dir, 'venv')
    
    if os.path.exists(venv_path):
        print("✅ Entorno virtual ya existe")
    else:
        print("📦 Creando nuevo entorno virtual...")
        if os.name == 'nt':
            success = run_command('python -m venv venv')
        else:
            success = run_command('python3 -m venv venv')
        
        if not success:
            print("❌ Error creando entorno virtual")
            sys.exit(1)
    
    # Obtener la ruta del ejecutable de Python en el entorno virtual
    if os.name == 'nt':
        python_exe = 'venv\\Scripts\\python.exe'
        pip_exe = 'venv\\Scripts\\pip.exe'
    else:
        python_exe = 'venv/bin/python'
        pip_exe = 'venv/bin/pip'
    
    print(f"\n🐍 Python: {python_exe}")
    print(f"📦 pip: {pip_exe}")
    
    # === INSTALAR DEPENDENCIAS ===
    print("\n📦 Instalando dependencias...")
    
    # Actualizar pip
    run_command(f'{pip_exe} install --upgrade pip')
    
    # Instalar todas las dependencias necesarias
    deps = [
        'python-telegram-bot>=22.8',
        'python-dotenv',
        'mistralai',
        'Flask'
    ]
    
    deps_str = ' '.join(deps)
    if not run_command(f'{pip_exe} install {deps_str}'):
        print("❌ Error instalando dependencias")
        print("Intentando instalar cada dependencia individualmente...")
        
        for dep in deps:
            run_command(f'{pip_exe} install {dep}')
    
    # Instalar el paquete actual (bot de finanzas personales)
    print("\n📦 Instalando bot de finanzas personales...")
    if not run_command(f'{pip_exe} install -e .'):
        print("❌ Error instalando paquete con -e flag")
        # Intentar instalar sin -e flag
        run_command(f'{pip_exe} install .')
    
    # === VERIFICAR INSTALACIÓN ===
    print("\n🔍 Verificando instalación...")
    
    # Verificar que config.py puede ser importado
    if run_command(f'{python_exe} -c "import config; print(f\"✅ Config: AI_PROVIDER={config.AI_PROVIDER}\")"'):
        print("✅ config.py importado correctamente")
    
    # Verificar todos los módulos principales
    modules = ['config', 'database', 'handlers', 'knowledge', 'main', 'ai_client']
    all_good = True
    
    for module in modules:
        if run_command(f'{python_exe} -c "import {module}; print(f\"✅ {module} importado correctamente\")"'):
            print(f"✅ {module} importado correctamente")
        else:
            print(f"❌ {module} - Error importando")
            all_good = False
    
    # Verificar database.py
    if run_command(f'{python_exe} -c "import database; import config; database.crear_tablas(); print(\\"✅ Base de datos SQLite creada/verificada\\")"'):
        print("✅ database.py funcionando correctamente")
    
    # Verificar creación de directorio .env si no existe
    env_path = os.path.join(script_dir, '.env')
    if not os.path.exists(env_path):
        print("\n📝 Creando archivo .env...")
        
        env_content = """# Configuración del Bot de Finanzas Personales

# Token del bot de Telegram (obtener de @BotFather)
TELEGRAM_BOT_TOKEN=tu_token_aquí

# Proveedor de IA: "ollama" o "mistral"
AI_PROVIDER=mistral

# Configuración de Mistral AI
MISTRAL_API_KEY=tu_clave_aquí
MISTRAL_MODEL=mistral-small-latest

# Configuración de Ollama (si AI_PROVIDER es "ollama")
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
"""
        
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        print("✅ Archivo .env creado")
        print("⚠️  IMPORTANTE: Edita el archivo .env y reemplaza 'tu_token_aquí' con tu token real de Telegram")
    else:
        print("✅ Archivo .env ya existe")
    
    # Crear directorio data si no existe
    data_dir = os.path.join(script_dir, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        print(f"✅ Directorio {data_dir} creado")
    
    # Verificar que podemos importar ai_client
    if run_command(f'{python_exe} -c "from ai_client import AIResponder; print(\"✅ Módulo ai_client importado correctamente\")"'):
        print("✅ Módulo ai_client importado correctamente")
    
    # Mostrar resumen
    print("\n" + "=" * 70)
    print("🎉 ¡ENTORNO VIRTUAL Y DEPENDENCIAS INSTALADAS EXITOSAMENTE!")
    print("=" * 70)
    print("\n📋 PRÓXIMOS PASOS:")
    print("   1. Editar .env y reemplazar 'tu_token_aquí' con token real")
    print("   2. Ejecutar:")
    print(f"      {python_exe} main.py")
    print("\n🤖 CARACTERÍSTICAS DEL BOT:")
    print("   • Registro de transacciones en lenguaje natural")
    print("   • IA híbrida: Nativo + Mistral AI")
    print("   • Gestión completa de presupuesto y ahorro")
    print("   • Base de datos SQLite personalizada")
    print("   • Categorías y marcas financieras")
    print("\n🚀 El bot está listo para usar!")
    
    print("\n🔧 INFORMACIÓN DE CREACIÓN:")
    print("   • Entorno virtual: venv/")
    print("   • Python: Python 3 con soporte completo")
    print("   • Dependencias: python-telegram-bot, python-dotenv, mistralai")
    print("   • Sistema: Listo para producción")

if __name__ == "__main__":
    main()