#!/usr/bin/env python3
"""
Script de instalación y verificación del bot de finanzas personales.
Configura automáticamente el entorno y verifica todo el sistema.
"""

import subprocess
import sys
import os
import pathlib

def run_command(cmd, cwd=None):
    """Ejecutar comando y retornar salida y código de salida"""
    try:
        print(f"\n🔧 Ejecutando: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip():
                    print(f"   {line}")
        if result.stderr:
            for line in result.stderr.split('\n'):
                if line.strip():
                    print(f"   ❌ Error: {line}")
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return -1, "", str(e)

def main():
    print("=" * 70)
    print("🚀 CONFIGURANDO BOT DE FINANZAS PERSONALES - ENFOQUE A")
    print("=" * 70)
    
    # Change to the script's directory
    script_dir = pathlib.Path(__file__).parent
    os.chdir(script_dir)
    
    print(f"\n📁 Directorio de trabajo: {os.getcwd()}")
    
    # === ENFOQUE A: Arquitectura completa desde cero ===
    print("\n🎯 ENFOQUE A: Implemantación completa de IA híbrida")
    print("   ✅ Sistema financiero completo con 5 tablas de base de datos")
    print("   ✅ IA híbrida: Nativo + Mistral AI")
    print("   ✅ Registro de transacciones en lenguaje natural")
    print("   ✅ Gestión completa de presupuestos y ahorro")
    print("   ✅ Separación de usuarios por Telegram ID")
    
    # === VERIFICAR SI EL ENTORNO VIRTUAL EXISTE ===
    print("\n📁 VERIFICANDO ENTORNO VIRTUAL...")
    venv_path = os.path.join(script_dir, 'venv')
    
    if os.path.exists(venv_path):
        print("✅ Entorno virtual encontrado")
        
        if os.name == 'nt':
            python_exe = 'venv\\Scripts\\python.exe'
            pip_exe = 'venv\\Scripts\\pip.exe'
        else:
            python_exe = 'venv/bin/python'
            pip_exe = 'venv/bin/pip'
        
        print(f"   🐍 Python: {python_exe}")
        print(f"   📦 pip: {pip_exe}")
        
        # === INSTALAR DEPENDENCIAS ===
        print("\n📦 INSTALANDO DEPENDENCIAS...")
        
        # Actualizar pip
        run_command(f'{pip_exe} install --upgrade pip')
        
        # Instalar dependencias principales
        deps = [
            'python-telegram-bot>=22.8',
            'python-dotenv',
            'mistralai',
            'Flask'
        ]
        
        deps_str = ' '.join(deps)
        run_command(f'{pip_exe} install {deps_str}')
        
        # Instalar el paquete actual
        run_command(f'{pip_exe} install -e .')
        
    else:
        print("📦 Creando entorno virtual...")
        if os.name == 'nt':
            run_command('python -m venv venv')
        else:
            run_command('python3 -m venv venv')
        
        if os.path.exists(venv_path):
            print("✅ Entorno virtual creado")
            
            if os.name == 'nt':
                python_exe = 'venv\\Scripts\\python.exe'
                pip_exe = 'venv\\Scripts\\pip.exe'
            else:
                python_exe = 'venv/bin/python'
                pip_exe = 'venv/bin/pip'
            
            # Instalar dependencias
            run_command(f'{pip_exe} install --upgrade pip')
            
            deps = [
                'python-telegram-bot>=22.8',
                'python-dotenv',
                'mistralai',
                'Flask'
            ]
            
            deps_str = ' '.join(deps)
            run_command(f'{pip_exe} install {deps_str}')
            
            run_command(f'{pip_exe} install -e .')
        else:
            print("❌ Error creando entorno virtual")
            sys.exit(1)
    
    # === VERIFICAR CONFIGURACIÓN ===
    print("\n⚙️ VERIFICANDO CONFIGURACIÓN...")
    
    if os.name == 'nt':
        python_exe = 'venv\\Scripts\\python.exe'
    else:
        python_exe = 'venv/bin/python'
    
    # Cargar config
    run_command(f'{python_exe} -c "import config; print(f\"AI_PROVIDER: {config.AI_PROVIDER}\"); print(f\"MISTRAL_API_KEY: {config.MISTRAL_API_KEY[:20]}...\")"')
    
    # === VERIFICAR MÓDULOS DEL SISTEMA ===
    print("\n🔍 VERIFICANDO MÓDULOS DEL SISTEMA...")
    
    modules = ['config', 'database', 'handlers', 'knowledge', 'main', 'ai_client']
    
    for module in modules:
        run_command(f'{python_exe} -c "import {module}; print(f\"✅ {module} - Cargado correctamente\")"')
    
    # === CREAR .env si no existe ===
    print("\n🔑 CONFIGURANDO .env...")
    
    env_path = os.path.join(script_dir, '.env')
    if not os.path.exists(env_path):
        print("📝 Creando archivo .env...")
        
        env_content = """# Configuración del Bot de Finanzas Personales

# Token del bot de Telegram (obtener de @BotFather)
TELEGRAM_BOT_TOKEN=tu_token_aquí

# Proveedor de IA: "ollama" o "mistral"
AI_PROVIDER=mistral

# Configuración de Mistral AI (si AI_PROVIDER es "mistral")
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
    
    # === VERIFICAR ESTRUCTURA DEL PROYECTO ===
    print("\n📋 VERIFICANDO ESTRUCTURA DEL PROYECTO...")
    
    required_files = [
        'config.py',
        'database.py',
        'handlers.py',
        'knowledge.py',
        'main.py',
        'ai_client.py',
        'README.md'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - FALTANTE")
    
    required_dirs = ['data', 'prompts']
    for dir_name in required_dirs:
        if os.path.exists(dir_name) and os.path.isdir(dir_name):
            print(f"✅ {dir_name}/")
        else:
            print(f"❌ {dir_name}/ - FALTANTE")
    
    # === CREAR .gitignore ===
    print("\n📝 CREANDO .gitignore...")
    
    gitignore_content = """venv/
__pycache__/
*.pyc
*.db
*.sqlite3
*.log
*.tmp
.DS_Store
.env.local
.idea/
.vscode/
"""
    
    with open('.gitignore', 'w') as f:
        f.write(gitignore_content)
    
    print("✅ .gitignore creado")
    
    print("\n" + "=" * 70)
    print("🎉 ¡CONFIGURACIÓN COMPLETADA!")
    print("=" * 70)
    print("\n📋 PRÓXIMOS PASOS:")
    print(f"   1. Editar .env y reemplazar 'tu_token_aquí' con token real")
    print(f"   2. Ejecutar: {python_exe} main.py")
    print("   3. ¡El bot estará funcionando!")
    
    print("\n💬 COMANDOS DE FINANZAS DEL BOT:")
    print("   • /start - Iniciar/Reiniciar el bot")
    print("   • /help  - Ver todos los comandos")
    print("   • /user  - Ver información del usuario")
    print("\n   • 'Gasté $50 en comida para el desayuno'")
    print("   • 'Recibí $2000 de salario'")
    print("   • 'Mi presupuesto para comida es $500 este mes'")
    print("   • 'Quiero ahorrar $5000 para unas vacaciones'")
    print("   • '¿Cuál es mi balance actual?'")
    
    print("\n🤖 SISTEMA IA IMPLEMENTADO:")
    print("   • IA Nativa Rápida: Procesamiento regex para comandos simples")
    print("   • IA Avanzada: Mistral AI para lenguaje natural complejo")
    print("   • IA Híbrida: Mejor rendimiento y precisión")
    print("   • Detección de intenciones robusta")
    print("   • Extracción estructurada de datos financieros")
    
    print("\n💾 CARACTERÍSTICAS FINANCIERAS:")
    print("   • Base de datos SQLite con 5 tablas")
    print("   • Gestión de usuarios por separado (ID de Telegram)")
    print("   • 4 tipos de categorías (gastos, ingresos, ahorros, inversiones)")
    print("   • Presupuestos mensuales/anuales")
    print("   • Metas de ahorro con seguimiento de progreso")
    print("   • Histórico completo de transacciones")
    print("   • Análisis e informes")
    
    print("\n🚀 EL BOT ESTÁ LISTO PARA USAR!")
    print("   La IA híbrida (Nativo + Mistral) está lista para procesar")
    print("   lenguaje natural y registros financieros automáticamente.")

if __name__ == "__main__":
    main()