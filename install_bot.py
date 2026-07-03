#!/usr/bin/env python3
"""
Script de configuración del bot de finanzas personales
Configura el entorno virtual y todas las dependencias.
"""

import subprocess
import sys
import os
import pathlib

def run_command(cmd, cwd=None, check=True):
    """Ejecuta un comando y retorna la salida"""
    print(f"🔧 Ejecutando: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
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
    print("🚀 CONFIGURANDO BOT DE FINANZAS PERSONALES - ENFOQUE A")
    print("=" * 70)
    
    # Change to the script's directory
    script_dir = pathlib.Path(__file__).parent
    os.chdir(script_dir)
    
    print(f"\n📁 Directorio de trabajo: {os.getcwd()}")
    
    # Check if virtual environment exists
    venv_path = os.path.join(script_dir, 'venv')
    
    if os.path.exists(venv_path):
        print("✅ Entorno virtual encontrado")
    else:
        print("📦 Creando entorno virtual...")
        if os.name == 'nt':
            success = run_command('python -m venv venv')
        else:
            success = run_command('python3 -m venv venv')
        
        if not success:
            print("❌ Error creando entorno virtual")
            sys.exit(1)
    
    # Setup virtual environment
    if os.name == 'nt':
        python_exe = 'venv\\Scripts\\python.exe'
        pip_exe = 'venv\\Scripts\\pip.exe'
    else:
        python_exe = 'venv/bin/python'
        pip_exe = 'venv/bin/pip'
    
    print(f"\n🐍 Python: {python_exe}")
    print(f"📦 pip: {pip_exe}")
    
    # Install dependencies
    print("\n📦 Instalando dependencias...")
    
    # Upgrade pip
    run_command(f'{pip_exe} install --upgrade pip')
    
    # Install main dependencies
    deps = [
        'python-telegram-bot>=22.8',
        'python-dotenv',
        'mistralai',
        'Flask'
    ]
    
    deps_str = ' '.join(deps)
    if not run_command(f'{pip_exe} install {deps_str}'):
        print("❌ Error installing dependencies")
        sys.exit(1)
    
    # Install the package itself
    print("\n📦 Instalando bot de finanzas personales...")
    if not run_command(f'{pip_exe} install -e .'):
        print("❌ Error installing package")
        # Try without -e flag
        if not run_command(f'{pip_exe} install .'):
            print("❌ Error installing package without -e flag")
            sys.exit(1)
    
    # Verify installation
    print("\n🔍 Verificando instalación...")
    
    # Check if config.py can be imported
    if run_command(f'{python_exe} -c "import config; print(f\"✅ Config: AI_PROVIDER={config.AI_PROVIDER}\")"'):
        print("✅ config.py importado correctamente")
    
    # Check if all modules can be imported
    modules = ['config', 'database', 'handlers', 'knowledge', 'main', 'ai_client']
    all_good = True
    
    for module in modules:
        if run_command(f'{python_exe} -c "import {module}; print(f\"✅ {module} importado correctamente\")"'):
            print(f"✅ {module} importado correctamente")
        else:
            print(f"❌ {module} - Error importando")
            all_good = False
    
    # Verify database.py
    print("\n🗄️ Verificando base de datos...")
    if run_command(f'{python_exe} -c "
import database
import config
database.crear_tablas()
print(\"✅ Base de datos creada/verificada\")
"'):
        print("✅ Base de datos SQLite funcionando")
    
    # Check if .env exists
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
"""
        
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        print("✅ Archivo .env creado")
        print("⚠️ IMPORTANTE: Edita el archivo .env y reemplaza 'tu_token_aquí' con tu token real de Telegram")
    else:
        print("✅ Archivo .env ya existe")
    
    # Show project structure
    print("\n📋 ESTRUCTURA DEL PROYECTO:")
    required_files = ['config.py', 'database.py', 'handlers.py', 'knowledge.py', 'main.py', 'ai_client.py', 'README.md']
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - FALTANTE")
    
    print("\n" + "=" * 70)
    print("🎉 ¡CONFIGURACIÓN COMPLETADA!")
    print("=" * 70)
    print("\n📋 PRÓXIMOS PASOS:")
    print("   1. Abrir .env y reemplazar 'tu_token_aquí' con token real de Telegram")
    print("   2. Ejecutar:")
    print(f"      {python_exe} main.py")
    print("   3. ¡El bot estará funcionando!")
    
    print("\n💬 COMANDOS DEL BOT:")
    print("   • /start - Iniciar/Reiniciar el bot")
    print("   • /help  - Ver todos los comandos")
    print("   • /user  - Ver información del usuario")
    print("\n   • 'Gasté $50 en comida para el desayuno'")
    print("   • 'Recibí $2000 de salario'")
    print("   • 'Mi presupuesto para comida es $500 este mes'")
    print("   • 'Quiero ahorrar $5000 para unas vacaciones'")
    print("   • '¿Cuál es mi balance actual?'")
    
    print("\n🤖 SISTEMA IA INTEGRADO:")
    print("   • IA Nativa: Rápida para comandos simples")
    print("   • IA Avanzada: Mistral AI para lenguaje complejo")
    print("   • IA Híbrida: Mejor rendimiento y precisión")
    print("   • Detección de intenciones robusta")
    print("   • Extracción estructurada de datos financieros")
    
    print("\n💰 CARACTERÍSTICAS FINANCIERAS:")
    print("   • Base de datos SQLite con 5 tablas")
    print("   • Usuarios por separado (ID de Telegram)")
    print("   • 4 tipos de categorías (gastos, ingresos, ahorros, inversiones)")
    print("   • Presupuestos mensuales/anuales")
    print("   • Metas de ahorro con seguimiento de progreso")
    print("   • Histórico completo de transacciones")
    print("   • Análisis e informes")
    
    print("\n🚀 EL BOT ESTÁ LISTO PARA USAR!")
    print("   Con IA híbrida (Nativo + Mistral), el bot puede procesar")
    print("   lenguaje natural y registros financieros automáticamente.")

if __name__ == "__main__":
    main()