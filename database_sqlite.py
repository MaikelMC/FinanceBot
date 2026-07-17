"""
database.py - Sistema financiero de gestión para finanzas personales
Maneja transacciones, presupuestos, metas de ahorro y categorías de usuarios separados.
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Obtiene una conexión a la base de datos."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def crear_tablas():
    """Crea todas las tablas necesarias si no existen."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER NOT NULL UNIQUE,
            nombre TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('gastos', 'ingresos', 'ahorros', 'inversiones')),
            descripcion TEXT,
            icono_color TEXT DEFAULT '#3498db',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            categoria_id INTEGER,
            tipo TEXT NOT NULL CHECK(tipo IN ('gasto', 'ingreso')),
            cantidad REAL NOT NULL,
            descripcion TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            FOREIGN KEY (categoria_id) REFERENCES categorias (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presupuestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            categoria_id INTEGER,
            cantidad_planejada REAL NOT NULL,
            cantidad_gastada REAL DEFAULT 0.0,
            periodo TEXT NOT NULL CHECK(periodo IN ('mensual', 'anual')),
            fecha_inicio DATE NOT NULL,
            fecha_fin DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            FOREIGN KEY (categoria_id) REFERENCES categorias (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metas_ahorro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            objetivo REAL NOT NULL,
            cantidad_actual REAL DEFAULT 0.0,
            fecha_inicio DATE NOT NULL,
            fecha_meta DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    """)

    conn.commit()
    conn.close()


def obtener_o_crear_usuario(telegram_user_id: int, nombre: str) -> Dict[str, Any]:
    """Obtiene un usuario existente o lo crea si no existe."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios WHERE telegram_user_id = ?", (telegram_user_id,))
    usuario = cursor.fetchone()

    if usuario:
        conn.close()
        return dict(usuario)

    cursor.execute(
        "INSERT INTO usuarios (telegram_user_id, nombre) VALUES (?, ?)",
        (telegram_user_id, nombre)
    )
    usuario_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {"id": usuario_id, "telegram_user_id": telegram_user_id, "nombre": nombre}


def obtener_usuario(telegram_user_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un usuario por su ID de Telegram."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE telegram_user_id = ?", (telegram_user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def crear_categoria(usuario_id: int, nombre: str, tipo: str, descripcion: str = "", icono_color: str = "") -> Dict[str, Any]:
    """Crea una nueva categoría para un usuario."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO categorias (usuario_id, nombre, tipo, descripcion, icono_color) VALUES (?, ?, ?, ?, ?)",
        (usuario_id, nombre, tipo, descripcion, icono_color)
    )
    categoria_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": categoria_id,
        "usuario_id": usuario_id,
        "nombre": nombre,
        "tipo": tipo,
        "descripcion": descripcion,
        "icono_color": icono_color
    }


def obtener_categorias(usuario_id: int, tipo: Optional[str] = None) -> List[Dict[str, Any]]:
    """Obtiene todas las categorías de un usuario, opcionalmente filtradas por tipo."""
    conn = get_connection()
    cursor = conn.cursor()

    if tipo:
        cursor.execute(
            "SELECT * FROM categorias WHERE usuario_id = ? AND tipo = ? ORDER BY nombre",
            (usuario_id, tipo)
        )
    else:
        cursor.execute(
            "SELECT * FROM categorias WHERE usuario_id = ? ORDER BY tipo, nombre",
            (usuario_id,)
        )

    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def agregar_transaccion(usuario_id: int, categoria_id: int, tipo: str, cantidad: float, descripcion: str = "") -> Dict[str, Any]:
    """Agrega una nueva transacción para un usuario."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO transacciones (usuario_id, categoria_id, tipo, cantidad, descripcion)
        VALUES (?, ?, ?, ?, ?)
        """,
        (usuario_id, categoria_id, tipo, cantidad, descripcion)
    )
    transaccion_id = cursor.lastrowid

    # Si es un gasto, actualiza la cantidad gastada del presupuesto
    if tipo == 'gasto' and categoria_id:
        cursor.execute("SELECT cantidad_planejada, cantidad_gastada FROM presupuestos WHERE categoria_id = ? ORDER BY fecha_inicio DESC LIMIT 1", (categoria_id,))
        presupuesto = cursor.fetchone()
        if presupuesto:
            nueva_cantidad_gastada = presupuesto['cantidad_gastada'] + cantidad
            cursor.execute(
                "UPDATE presupuestos SET cantidad_gastada = ? WHERE id = ?",
                (nueva_cantidad_gastada, cursor.lastrowid)
            )

    conn.commit()
    conn.close()

    return {
        "id": transaccion_id,
        "usuario_id": usuario_id,
        "categoria_id": categoria_id,
        "tipo": tipo,
        "cantidad": cantidad,
        "descripcion": descripcion
    }


def obtener_transacciones(usuario_id: int, limite: int = 50, tipo: Optional[str] = None) -> List[Dict[str, Any]]:
    """Obtiene transacciones de un usuario ordenadas por fecha reciente.
    Si `tipo` es 'gasto' o 'ingreso', filtra por ese tipo."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT t.id, t.tipo, t.cantidad, t.descripcion, t.fecha,
               c.nombre as categoria_nombre, c.tipo as categoria_tipo, c.descripcion as categoria_descripcion
        FROM transacciones t
        LEFT JOIN categorias c ON t.categoria_id = c.id
        WHERE t.usuario_id = ?
    """
    params = [usuario_id]

    if tipo in ("gasto", "ingreso"):
        query += " AND t.tipo = ?"
        params.append(tipo)

    query += " ORDER BY t.fecha DESC LIMIT ?"
    params.append(limite)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obtener_balance(usuario_id: int, fecha_inicio: Optional[str] = None) -> Dict[str, Any]:
    """Obtiene el balance financiero de un usuario."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT tipo, SUM(cantidad) as total
        FROM transacciones
        WHERE usuario_id = ?
    """
    params = [usuario_id]

    if fecha_inicio:
        query += " AND fecha >= ?"
        params.append(fecha_inicio)

    query += " GROUP BY tipo"

    cursor.execute(query, params)
    balances = cursor.fetchall()
    conn.close()

    resultado = {"ingresos": 0.0, "gastos": 0.0}
    for row in balances:
        if row['tipo'] == 'ingreso':
            resultado["ingresos"] = row['total']
        elif row['tipo'] == 'gasto':
            resultado["gastos"] = row['total']

    resultado["neto"] = resultado["ingresos"] - resultado["gastos"]
    return resultado


def obtener_presupuestos(usuario_id: int) -> List[Dict[str, Any]]:
    """Obtiene todos los presupuestos activos de un usuario."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.id, p.cantidad_planejada, p.cantidad_gastada, p.periodo,
               p.fecha_inicio, p.fecha_fin, c.nombre as categoria_nombre
        FROM presupuestos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.usuario_id = ?
        ORDER BY p.fecha_inicio DESC
        """,
        (usuario_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def crear_presupuesto(usuario_id: int, categoria_id: int, cantidad_planejada: float, periodo: str, fecha_inicio: str, fecha_fin: Optional[str] = None) -> Dict[str, Any]:
    """Crea un nuevo presupuesto para un usuario."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO presupuestos (usuario_id, categoria_id, cantidad_planejada, cantidad_gastada, periodo, fecha_inicio, fecha_fin)
        VALUES (?, ?, ?, 0.0, ?, ?, ?)
        """,
        (usuario_id, categoria_id, cantidad_planejada, 0.0, periodo, fecha_inicio, fecha_fin)
    )
    presupuesto_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": presupuesto_id,
        "usuario_id": usuario_id,
        "categoria_id": categoria_id,
        "cantidad_planejada": cantidad_planejada,
        "cantidad_gastada": 0.0,
        "periodo": periodo,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin
    }


def obtener_metas_ahorro(usuario_id: int) -> List[Dict[str, Any]]:
    """Obtiene todas las metas de ahorro de un usuario."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM metas_ahorro WHERE usuario_id = ? ORDER BY fecha_meta",
        (usuario_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def actualizar_meta_ahorro(meta_id: int, cantidad: float) -> bool:
    """Actualiza el progreso de una meta de ahorro."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE metas_ahorro SET cantidad_actual = cantidad_actual + ? WHERE id = ?",
        (cantidad, meta_id)
    )
    conn.commit()
    actualizado = cursor.rowcount > 0
    conn.close()
    return actualizado


def contar_transacciones(usuario_id: int) -> Dict[str, Any]:
    """Retorna conteos de transacciones y categorías."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM transacciones WHERE usuario_id = ?", (usuario_id,))
    total = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT c.tipo, COUNT(*) as cantidad FROM transacciones t JOIN categorias c ON t.categoria_id = c.id WHERE t.usuario_id = ? GROUP BY c.tipo",
        (usuario_id,)
    )
    por_tipo = {row["tipo"]: row["cantidad"] for row in cursor.fetchall()}

    conn.close()
    return {"total": total, **por_tipo}


def eliminar_transacciones(usuario_id: int) -> int:
    """Elimina todas las transacciones de un usuario. Retorna la cantidad eliminada."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transacciones WHERE usuario_id = ?", (usuario_id,))
    eliminadas = cursor.rowcount
    conn.commit()
    conn.close()
    return eliminadas


def obtener_transaccion_por_id(usuario_id: int, transaccion_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene una transacción específica por ID, verificando que pertenezca al usuario."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT t.id, t.tipo, t.cantidad, t.descripcion, t.fecha, t.categoria_id,
               c.nombre as categoria_nombre, c.tipo as categoria_tipo
        FROM transacciones t
        LEFT JOIN categorias c ON t.categoria_id = c.id
        WHERE t.id = ? AND t.usuario_id = ?
        """,
        (transaccion_id, usuario_id)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def actualizar_transaccion(usuario_id: int, transaccion_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Actualiza campos de una transacción. Campos soportados:
    tipo, cantidad, descripcion, categoria_id, fecha.
    Retorna la transacción actualizada o None si no se encontró.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM transacciones WHERE id = ? AND usuario_id = ?",
        (transaccion_id, usuario_id)
    )
    if not cursor.fetchone():
        conn.close()
        return None

    campos_permitidos = {"tipo", "cantidad", "descripcion", "categoria_id", "fecha"}
    campos = {k: v for k, v in kwargs.items() if k in campos_permitidos and v is not None}

    if not campos:
        conn.close()
        return None

    sets = ", ".join(f"{k} = ?" for k in campos)
    valores = list(campos.values()) + [transaccion_id, usuario_id]
    cursor.execute(
        f"UPDATE transacciones SET {sets} WHERE id = ? AND usuario_id = ?",
        valores
    )
    conn.commit()

    cursor.execute(
        """
        SELECT t.id, t.tipo, t.cantidad, t.descripcion, t.fecha, t.categoria_id,
               c.nombre as categoria_nombre, c.tipo as categoria_tipo
        FROM transacciones t
        LEFT JOIN categorias c ON t.categoria_id = c.id
        WHERE t.id = ? AND t.usuario_id = ?
        """,
        (transaccion_id, usuario_id)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def eliminar_transaccion(usuario_id: int, transaccion_id: int) -> bool:
    """Elimina una transacción específica por ID. Retorna True si se eliminó."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM transacciones WHERE id = ? AND usuario_id = ?",
        (transaccion_id, usuario_id)
    )
    eliminada = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return eliminada