# PROMPT PARA OPENCODE / CURSOR / CLAUDE

Eres un experto en Python y bots de Telegram. Tengo un bot de finanzas personales bien estructurado (según el STACK.md anterior) que actualmente usa SQLite.

**Tarea:** Migra completamente la capa de base de datos de SQLite a **Google Sheets** usando la librería `gspread`.

### Requisitos específicos:

1. Crear una nueva clase `GoogleSheetsDB` en un archivo `database_gsheets.py` que reemplace `database.py`.

2. Mantener exactamente las mismas funciones públicas que ya existen:
   - crear_tablas() → (puede ser init_sheets)
   - agregar_transaccion(...)
   - obtener_transacciones(usuario_id, limite=50)
   - obtener_balance(usuario_id)
   - obtener_gastos(usuario_id)
   - obtener_ingresos(usuario_id)
   - etc. (todas las funciones usadas en knowledge.py y handlers.py)

3. Usar pandas para facilitar lecturas/escrituras cuando sea necesario.

4. Manejar correctamente las 5 tablas:
   - Usuarios
   - Categorias  
   - Transacciones (la más usada)
   - Presupuestos
   - Metas_Ahorro

5. Implementar caché ligero en memoria para mejorar velocidad (ya que Google Sheets es lento).

6. Mantener compatibilidad total con el resto del código (no romper handlers.py ni knowledge.py).

### Estructura deseada:
- Mantener el mismo estilo de código limpio y comentado del proyecto actual.
- Añadir manejo de errores amigable.
- Incluir función para inicializar todas las hojas con encabezados si no existen.

Genera:
- El archivo completo `database_gsheets.py`
- Las modificaciones necesarias en `config.py`, `main.py` y `knowledge.py`
- Actualización del `.env.example`
- Instrucciones breves de cómo integrar todo.

Prioriza **simplicidad** y **robustez**. El bot debe seguir funcionando exactamente igual para el usuario final, solo cambiando el backend de almacenamiento.

¡Comienza!
