"""
database_gsheets.py - Backend Google Sheets para el bot de finanzas personales
Reemplaza database.py usando gspread + pandas con caché en memoria.

Misma interfaz pública que database.py para compatibilidad total.
"""

import logging
import os
import json
import random
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import gspread
from gspread.exceptions import APIError
import pandas as pd
from gspread_dataframe import set_with_dataframe, get_as_dataframe

import config

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURACIÓN DE HOJAS (cada "tabla" es una hoja en el spreadsheet)
# ============================================================

SHEET_NAMES = {
    "usuarios": "usuarios",
    "categorias": "categorias",
    "transacciones": "transacciones",
    "presupuestos": "presupuestos",
    "metas_ahorro": "metas_ahorro",
    "notificaciones": "notificaciones",
    "monedas": "monedas",
}

# Columnas de cada hoja (deben coincidir con las claves de los dicts devueltos)
SHEET_COLUMNS = {
    "usuarios": ["id", "telegram_user_id", "nombre", "created_at", "updated_at"],
    "categorias": ["id", "usuario_id", "nombre", "tipo", "descripcion", "icono_color", "created_at"],
    "transacciones": ["id", "usuario_id", "categoria_id", "tipo", "cantidad", "descripcion", "moneda_id", "fecha", "created_at"],
    "presupuestos": ["id", "usuario_id", "categoria_id", "cantidad_planejada", "cantidad_gastada", "periodo", "fecha_inicio", "fecha_fin", "created_at"],
    "metas_ahorro": ["id", "usuario_id", "nombre", "objetivo", "cantidad_actual", "fecha_inicio", "fecha_meta", "created_at"],
    "notificaciones": ["id", "usuario_id", "version", "enviada_en"],
    "monedas": ["id", "usuario_id", "nombre", "simbolo", "abreviatura", "es_default", "created_at"],
}

LOCK = threading.Lock()


# ============================================================
# CLASE PRINCIPAL
# ============================================================

class GoogleSheetsDB:
    """Capa de persistencia sobre Google Sheets con caché en memoria."""

    def __init__(self):
        self._spreadsheet = None
        self._client = None
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_dirty: set = set()
        self._initialized = False
        self._next_ids: Dict[str, int] = {}
        self._flush_timer: Optional[threading.Timer] = None
        self._FLUSH_DELAY = 3.0  # segundos antes de flush real

    # ----------------------------------------------------------
    # INICIALIZACIÓN
    # ----------------------------------------------------------

    def init_sheets(self):
        """Abre o crea el spreadsheet y las hojas. Carga caché inicial."""
        if self._initialized:
            return

        creds_file = config.GOOGLE_SHEETS_CREDENTIALS
        creds_json = config.GOOGLE_SHEETS_CREDENTIALS_JSON
        sheet_id = config.GOOGLE_SHEETS_SPREADSHEET_ID

        if not sheet_id:
            raise ValueError("Falta GOOGLE_SHEETS_SPREADSHEET_ID en .env")

        # Support both file path and JSON string
        actual_creds_file = creds_file
        if creds_json:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(creds_json)
                actual_creds_file = f.name
            logger.info("Credentials JSON recibido como variable de entorno")
        elif creds_file and Path(creds_file).exists():
            actual_creds_file = creds_file
        else:
            raise ValueError(
                "Falta GOOGLE_SHEETS_CREDENTIALS o GOOGLE_SHEETS_CREDENTIALS_JSON en .env"
            )

        if not actual_creds_file or not Path(actual_creds_file).exists():
            raise FileNotFoundError(
                f"Archivo de credenciales Google Sheets no encontrado: {actual_creds_file}"
            )

        max_retries = 5
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                gc = gspread.service_account(filename=actual_creds_file)
                self._client = gc
                self._spreadsheet = gc.open_by_key(sheet_id)
                logger.info("Conectado a spreadsheet: %s", self._spreadsheet.title)
                break
            except gspread.SpreadsheetNotFound:
                raise ValueError(
                    f"No se encontró el spreadsheet con ID: {sheet_id}. "
                    "Verifica que el ID sea correcto y que el service account tenga acceso."
                )
            except APIError as e:
                status = e.response.status_code if e.response else 0
                if status in (429, 500, 502, 503) and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "Google Sheets temporalmente no disponible (HTTP %d, intento %d/%d). "
                        "Reintentando en %.1fs...",
                        status, attempt + 1, max_retries, delay,
                    )
                    time.sleep(delay)
                else:
                    raise ConnectionError(f"Error conectando a Google Sheets: {e}")
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "Error conectando a Google Sheets (intento %d/%d): %s. "
                        "Reintentando en %.1fs...",
                        attempt + 1, max_retries, e, delay,
                    )
                    time.sleep(delay)
                else:
                    raise ConnectionError(
                        f"Error conectando a Google Sheets después de {max_retries} intentos: {e}"
                    )

        self._ensure_sheets()
        self._load_all_cache()
        self._initialized = True
        logger.info("Google Sheets DB inicializada correctamente.")

    def _ensure_sheets(self):
        """Crea las hojas con sus encabezados si no existen."""
        existing = {ws.title for ws in self._spreadsheet.worksheets()}

        for name, cols in SHEET_COLUMNS.items():
            if name not in existing:
                ws = self._spreadsheet.add_worksheet(title=name, rows=1000, cols=len(cols))
                ws.append_row(cols)
                logger.info("Hoja creada: %s", name)
            else:
                ws = self._spreadsheet.worksheet(name)
                header = ws.row_values(1)
                if header != cols:
                    logger.warning(
                        "Hoja '%s' tiene encabezados distintos: %s. Se esperaba: %s",
                        name, header, cols
                    )

    def _load_all_cache(self):
        """Carga todas las hojas a la caché en memoria."""
        for name in SHEET_COLUMNS:
            self._load_sheet(name)

    def _load_sheet(self, name: str):
        """Carga una hoja a la caché."""
        try:
            ws = self._spreadsheet.worksheet(name)
            records = ws.get_all_records()
            # Normalizar: asegurar que todos los campos existen y tipos correctos
            rows = []
            for r in records:
                row = {col: r.get(col, "") for col in SHEET_COLUMNS[name]}
                # Castear campos numéricos para evitar strings en la caché
                if "cantidad" in row:
                    row["cantidad"] = self._parse_number_locale_aware(row["cantidad"])
                if "cantidad_planejada" in row:
                    row["cantidad_planejada"] = self._parse_number_locale_aware(row["cantidad_planejada"])
                if "cantidad_gastada" in row:
                    row["cantidad_gastada"] = self._parse_number_locale_aware(row["cantidad_gastada"])
                if "cantidad_actual" in row:
                    row["cantidad_actual"] = self._parse_number_locale_aware(row["cantidad_actual"])
                if "objetivo" in row:
                    row["objetivo"] = self._parse_number_locale_aware(row["objetivo"])
                if "moneda_id" in row:
                    try:
                        val = row["moneda_id"]
                        row["moneda_id"] = int(val) if val != "" and val is not None else None
                    except (TypeError, ValueError):
                        row["moneda_id"] = None
                rows.append(row)
            self._cache[name] = rows

            # Calcular próximo ID
            if rows:
                ids = [int(r["id"]) for r in rows if str(r.get("id", "")).isdigit()]
                self._next_ids[name] = max(ids) + 1 if ids else 1
            else:
                self._next_ids[name] = 1
        except Exception as e:
            logger.error("Error cargando hoja '%s': %s", name, e)
            self._cache[name] = []
            self._next_ids[name] = 1

    def _flush_sheet(self, name: str):
        """Escribe la caché modificada de vuelta a la hoja con formato numérico explícito."""
        if name not in self._cache_dirty:
            return
        try:
            ws = self._spreadsheet.worksheet(name)
            cols = SHEET_COLUMNS[name]
            df = pd.DataFrame(self._cache[name], columns=cols)
            ws.clear()
            set_with_dataframe(ws, df, include_column_header=True, resize=True)

            # Aplicar formato numérico explícito a columnas monetarias
            # Esto evita que Google Sheets interprete mal los decimales según locale
            numeric_cols = self._get_numeric_columns(name)
            for col_name in numeric_cols:
                if col_name in cols:
                    col_idx = cols.index(col_name) + 1  # 1-indexed
                    col_letter = chr(ord('A') + col_idx - 1) if col_idx <= 26 else None
                    if col_letter:
                        ws.format(f"{col_letter}:{col_letter}", {
                            "numberFormat": {
                                "type": "NUMBER",
                                "pattern": "0.00"
                            }
                        })

            self._cache_dirty.discard(name)
        except Exception as e:
            logger.error("Error escribiendo hoja '%s': %s", name, e)

    def _schedule_flush(self):
        """Programa un flush diferido para evitar rate limiting."""
        if self._flush_timer:
            self._flush_timer.cancel()
        self._flush_timer = threading.Timer(self._FLUSH_DELAY, self.flush_all)
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def flush_all(self):
        """Fuerza escritura de todas las hojas sucias a Google Sheets."""
        for name in list(self._cache_dirty):
            self._flush_sheet(name)

    def _next_id(self, sheet: str) -> int:
        """Genera el próximo ID secuencial para una hoja."""
        nid = self._next_ids.get(sheet, 1)
        self._next_ids[sheet] = nid + 1
        return nid

    def _now(self) -> str:
        """Retorna timestamp actual en formato ISO."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _parse_number_locale_aware(self, value) -> float:
        """
        Parsea un número manejando ambos separadores decimales (punto y coma).
        Convención: en locales latinos, coma = decimal, punto = miles.
        En locales US/UK, punto = decimal, coma = miles.
        
        Estrategia:
        1. Si es int/float directo, retornar como float
        2. Intentar float() directo (funciona para punto decimal)
        3. Si falla y tiene coma: detectar si coma es decimal (últimos 1-2 dígitos)
           y normalizar reemplazando punto por nada y coma por punto
        4. Caso US con coma de miles: "1,234.56" -> reemplazar coma por nada
        """
        if value is None or value == "":
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        
        s = str(value).strip()
        
        # Caso 1: float directo (punto como decimal: "234.56" o "1,234.56")
        try:
            return float(s)
        except ValueError:
            pass
        
        # Caso 2: formato US con coma de miles ("1,234.56")
        if ',' in s and '.' in s:
            # Verificar si es formato US: coma antes que punto, y punto seguido de 1-2 dígitos al final
            comma_pos = s.find(',')
            dot_pos = s.rfind('.')
            if comma_pos < dot_pos and len(s) - dot_pos - 1 <= 2:
                # Formato US: eliminar comas de miles
                try:
                    return float(s.replace(',', ''))
                except ValueError:
                    pass
        
        # Caso 3: coma como decimal ("234,56" o "1.234,56")
        if ',' in s:
            parts = s.rsplit(',', 1)
            if len(parts) == 2 and len(parts[1]) <= 2 and parts[1].isdigit():
                # Coma es decimal: eliminar puntos de miles, cambiar coma por punto
                normalized = parts[0].replace('.', '').replace(',', '') + '.' + parts[1]
                try:
                    return float(normalized)
                except ValueError:
                    pass
        
        # Caso 4: solo puntos como separadores de miles ("1.234" -> 1234)
        # Solo si no hay coma y todos los grupos tienen 3 dígitos excepto el primero
        if '.' in s and ',' not in s:
            parts = s.split('.')
            if len(parts[-1]) == 3 and all(len(p) == 3 for p in parts[:-1]):
                try:
                    return float(s.replace('.', ''))
                except ValueError:
                    pass
        
        return 0.0

    def _get_numeric_columns(self, sheet_name: str) -> List[str]:
        """Retorna lista de columnas numéricas para una hoja dada."""
        numeric_map = {
            "transacciones": ["cantidad"],
            "presupuestos": ["cantidad_planejada", "cantidad_gastada"],
            "metas_ahorro": ["objetivo", "cantidad_actual"],
        }
        return numeric_map.get(sheet_name, [])

    # ----------------------------------------------------------
    # USUARIOS
    # ----------------------------------------------------------

    def obtener_o_crear_usuario(self, telegram_user_id: int, nombre: str) -> Dict[str, Any]:
        with LOCK:
            users = self._cache.get("usuarios", [])
            for u in users:
                if str(u.get("telegram_user_id", "")) == str(telegram_user_id):
                    return dict(u)

            now = self._now()
            uid = self._next_id("usuarios")
            nuevo = {
                "id": uid,
                "telegram_user_id": telegram_user_id,
                "nombre": nombre,
                "created_at": now,
                "updated_at": now,
            }
            users.append(nuevo)
            self._cache_dirty.add("usuarios")
            self._schedule_flush()
            logger.info("Usuario creado: %s (ID %d)", nombre, uid)
            return dict(nuevo)

    def obtener_usuario(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        users = self._cache.get("usuarios", [])
        for u in users:
            if str(u.get("telegram_user_id", "")) == str(telegram_user_id):
                return dict(u)
        return None

    # ----------------------------------------------------------
    # CATEGORÍAS
    # ----------------------------------------------------------

    def crear_categoria(self, usuario_id: int, nombre: str, tipo: str, descripcion: str = "", icono_color: str = "") -> Dict[str, Any]:
        with LOCK:
            cats = self._cache.get("categorias", [])
            cid = self._next_id("categorias")
            nueva = {
                "id": cid,
                "usuario_id": usuario_id,
                "nombre": nombre,
                "tipo": tipo,
                "descripcion": descripcion,
                "icono_color": icono_color or "#3498db",
                "created_at": self._now(),
            }
            cats.append(nueva)
            self._cache_dirty.add("categorias")
            self._schedule_flush()
            logger.info("Categoría creada: %s (tipo=%s) para usuario %d", nombre, tipo, usuario_id)
            return dict(nueva)

    def obtener_categorias(self, usuario_id: int, tipo: Optional[str] = None) -> List[Dict[str, Any]]:
        cats = self._cache.get("categorias", [])
        resultado = []
        for c in cats:
            if int(c.get("usuario_id", 0)) != usuario_id:
                continue
            if tipo and c.get("tipo") != tipo:
                continue
            resultado.append(dict(c))
        resultado.sort(key=lambda x: (x.get("tipo", ""), x.get("nombre", "")))
        return resultado

    # ----------------------------------------------------------
    # TRANSACCIONES
    # ----------------------------------------------------------

    def agregar_transaccion(self, usuario_id: int, categoria_id: int, tipo: str, cantidad: float, descripcion: str = "", moneda_id: Optional[int] = None) -> Dict[str, Any]:
        with LOCK:
            # Validar y normalizar cantidad
            try:
                cantidad = round(float(cantidad), 2)
            except (TypeError, ValueError):
                cantidad = 0.0
            if cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor a 0")

            # Si no se especifica moneda, usar la default del usuario
            if moneda_id is None:
                monedas = self.obtener_monedas(usuario_id)
                for m in monedas:
                    if m.get("es_default"):
                        moneda_id = m["id"]
                        break

            trans = self._cache.get("transacciones", [])
            tid = self._next_id("transacciones")
            now = self._now()
            nueva = {
                "id": tid,
                "usuario_id": usuario_id,
                "categoria_id": categoria_id,
                "tipo": tipo,
                "cantidad": cantidad,
                "descripcion": descripcion,
                "moneda_id": moneda_id or "",
                "fecha": now,
                "created_at": now,
            }
            trans.append(nueva)
            self._cache_dirty.add("transacciones")

            # Si es gasto, actualizar presupuesto correspondiente
            if tipo == "gasto" and categoria_id:
                self._actualizar_gasto_presupuesto(usuario_id, categoria_id, cantidad)

            self._schedule_flush()
            logger.info("Transacción registrada: %s $%.2f (usuario %d)", tipo, cantidad, usuario_id)
            return dict(nueva)

    def _actualizar_gasto_presupuesto(self, usuario_id: int, categoria_id: int, cantidad: float):
        """Actualiza cantidad_gastada en el presupuesto activo de la categoría."""
        pres = self._cache.get("presupuestos", [])
        candidatos = [
            p for p in pres
            if int(p.get("usuario_id", 0)) == usuario_id
            and str(p.get("categoria_id", "")) == str(categoria_id)
        ]
        if not candidatos:
            return
        # Ordenar por fecha_inicio descendente, tomar el más reciente
        candidatos.sort(key=lambda x: str(x.get("fecha_inicio", "")), reverse=True)
        target = candidatos[0]
        actual = float(target.get("cantidad_gastada", 0))
        target["cantidad_gastada"] = actual + cantidad
        self._cache_dirty.add("presupuestos")

    def obtener_transacciones(self, usuario_id: int, limite: int = 50, tipo: Optional[str] = None) -> List[Dict[str, Any]]:
        trans = self._cache.get("transacciones", [])
        cats = self._cache.get("categorias", [])

        # Build categoria lookup
        cat_lookup = {str(c["id"]): c for c in cats}

        resultado = []
        for t in trans:
            uid = int(t.get("usuario_id", 0))
            if uid != usuario_id:
                continue
            if tipo and t.get("tipo") != tipo:
                continue

            # Enriquecer con datos de categoría (JOIN manual)
            cat = cat_lookup.get(str(t.get("categoria_id", "")))
            row = dict(t)
            # Asegurar que cantidad es float
            try:
                row["cantidad"] = float(row.get("cantidad", 0))
            except (TypeError, ValueError):
                row["cantidad"] = 0.0
            if cat:
                row["categoria_nombre"] = cat.get("nombre", "")
                row["categoria_tipo"] = cat.get("tipo", "")
                row["categoria_descripcion"] = cat.get("descripcion", "")
            else:
                row["categoria_nombre"] = ""
                row["categoria_tipo"] = ""
                row["categoria_descripcion"] = ""

            resultado.append(row)

        # Ordenar por fecha descendente
        resultado.sort(key=lambda x: str(x.get("fecha", "")), reverse=True)
        return resultado[:limite]

    def obtener_transacciones_por_fecha(self, usuario_id: int, fecha_inicio: str, fecha_fin: str,
                                         tipo: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene transacciones en un rango de fechas (YYYY-MM-DD)."""
        trans = self._cache.get("transacciones", [])
        cats = self._cache.get("categorias", [])
        cat_lookup = {str(c["id"]): c for c in cats}

        resultado = []
        for t in trans:
            uid = int(t.get("usuario_id", 0))
            if uid != usuario_id:
                continue

            fecha_txn = str(t.get("fecha", ""))[:10]
            if fecha_txn < fecha_inicio or fecha_txn > fecha_fin:
                continue

            if tipo and t.get("tipo") != tipo:
                continue

            cat = cat_lookup.get(str(t.get("categoria_id", "")))
            row = dict(t)
            if cat:
                row["categoria_nombre"] = cat.get("nombre", "")
                row["categoria_tipo"] = cat.get("tipo", "")
                row["categoria_descripcion"] = cat.get("descripcion", "")
            else:
                row["categoria_nombre"] = ""
                row["categoria_tipo"] = ""
                row["categoria_descripcion"] = ""

            resultado.append(row)

        resultado.sort(key=lambda x: str(x.get("fecha", "")), reverse=True)
        return resultado

    def obtener_balance(self, usuario_id: int, fecha_inicio: Optional[str] = None) -> Dict[str, Any]:
        trans = self._cache.get("transacciones", [])
        monedas = self.obtener_monedas(usuario_id)
        moneda_lookup = {str(m["id"]): m for m in monedas}
        moneda_default = next((m for m in monedas if m.get("es_default")), None)

        ingresos = 0.0
        gastos = 0.0
        por_moneda: Dict[str, Dict[str, float]] = {}

        for t in trans:
            if int(t.get("usuario_id", 0)) != usuario_id:
                continue
            if fecha_inicio and str(t.get("fecha", "")) < fecha_inicio:
                continue
            try:
                cant = float(t.get("cantidad", 0))
            except (TypeError, ValueError):
                cant = 0.0

            if t.get("tipo") == "ingreso":
                ingresos += cant
            elif t.get("tipo") == "gasto":
                gastos += cant

            # Agrupar por moneda — fallback a default si moneda_id vacio
            mid = str(t.get("moneda_id", ""))
            if mid and mid in moneda_lookup:
                m = moneda_lookup[mid]
                key = m["abreviatura"]
            elif moneda_default:
                key = moneda_default["abreviatura"]
                mid = str(moneda_default["id"])
            else:
                key = "Sin moneda"

            if key not in por_moneda:
                por_moneda[key] = {"ingresos": 0.0, "gastos": 0.0, "simbolo": "", "nombre": ""}
            if mid in moneda_lookup:
                por_moneda[key]["simbolo"] = moneda_lookup[mid].get("simbolo", "$")
                por_moneda[key]["nombre"] = moneda_lookup[mid].get("nombre", key)
            elif moneda_default:
                por_moneda[key]["simbolo"] = moneda_default.get("simbolo", "$")
                por_moneda[key]["nombre"] = moneda_default.get("nombre", key)
            if t.get("tipo") == "ingreso":
                por_moneda[key]["ingresos"] += cant
            elif t.get("tipo") == "gasto":
                por_moneda[key]["gastos"] += cant

        return {
            "ingresos": round(ingresos, 2),
            "gastos": round(gastos, 2),
            "neto": round(ingresos - gastos, 2),
            "por_moneda": por_moneda,
        }

    def contar_transacciones(self, usuario_id: int) -> Dict[str, Any]:
        trans = self._cache.get("transacciones", [])
        cats = self._cache.get("categorias", [])
        cat_lookup = {str(c["id"]): c for c in cats}

        total = 0
        por_tipo: Dict[str, int] = {}

        for t in trans:
            if int(t.get("usuario_id", 0)) != usuario_id:
                continue
            total += 1
            cat = cat_lookup.get(str(t.get("categoria_id", "")))
            if cat:
                ct = cat.get("tipo", "otros")
                por_tipo[ct] = por_tipo.get(ct, 0) + 1

        return {"total": total, **por_tipo}

    # ----------------------------------------------------------
    # PRESUPUESTOS
    # ----------------------------------------------------------

    def crear_presupuesto(self, usuario_id: int, categoria_id: int, cantidad_planejada: float, periodo: str, fecha_inicio: str, fecha_fin: Optional[str] = None) -> Dict[str, Any]:
        with LOCK:
            pres = self._cache.get("presupuestos", [])
            pid = self._next_id("presupuestos")
            nuevo = {
                "id": pid,
                "usuario_id": usuario_id,
                "categoria_id": categoria_id,
                "cantidad_planejada": cantidad_planejada,
                "cantidad_gastada": 0.0,
                "periodo": periodo,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin or "",
                "created_at": self._now(),
            }
            pres.append(nuevo)
            self._cache_dirty.add("presupuestos")
            self._schedule_flush()
            logger.info("Presupuesto creado: $%.2f para categoría %d", cantidad_planejada, categoria_id)
            return dict(nuevo)

    def obtener_presupuestos(self, usuario_id: int) -> List[Dict[str, Any]]:
        pres = self._cache.get("presupuestos", [])
        cats = self._cache.get("categorias", [])
        cat_lookup = {str(c["id"]): c for c in cats}

        resultado = []
        for p in pres:
            if int(p.get("usuario_id", 0)) != usuario_id:
                continue
            row = dict(p)
            cat = cat_lookup.get(str(p.get("categoria_id", "")))
            row["categoria_nombre"] = cat.get("nombre", "") if cat else ""
            resultado.append(row)

        resultado.sort(key=lambda x: str(x.get("fecha_inicio", "")), reverse=True)
        return resultado

    # ----------------------------------------------------------
    # METAS DE AHORRO
    # ----------------------------------------------------------

    def obtener_metas_ahorro(self, usuario_id: int) -> List[Dict[str, Any]]:
        metas = self._cache.get("metas_ahorro", [])
        resultado = []
        for m in metas:
            if int(m.get("usuario_id", 0)) == usuario_id:
                resultado.append(dict(m))
        resultado.sort(key=lambda x: str(x.get("fecha_meta", "")))
        return resultado

    def actualizar_meta_ahorro(self, meta_id: int, cantidad: float) -> bool:
        with LOCK:
            metas = self._cache.get("metas_ahorro", [])
            for m in metas:
                if int(m.get("id", 0)) == meta_id:
                    actual = float(m.get("cantidad_actual", 0))
                    m["cantidad_actual"] = actual + cantidad
                    self._cache_dirty.add("metas_ahorro")
                    self._schedule_flush()
                    logger.info("Meta %d actualizada: +$%.2f", meta_id, cantidad)
                    return True
            return False

    # ----------------------------------------------------------
    # MONEDAS
    # ----------------------------------------------------------

    def crear_moneda(self, usuario_id: int, nombre: str, simbolo: str, abreviatura: str, es_default: bool = False) -> Dict[str, Any]:
        with LOCK:
            monedas = self._cache.get("monedas", [])
            if es_default:
                for m in monedas:
                    if int(m.get("usuario_id", 0)) == usuario_id:
                        m["es_default"] = 0

            mid = self._next_id("monedas")
            nueva = {
                "id": mid,
                "usuario_id": usuario_id,
                "nombre": nombre,
                "simbolo": simbolo,
                "abreviatura": abreviatura.upper(),
                "es_default": 1 if es_default else 0,
                "created_at": self._now(),
            }
            monedas.append(nueva)
            self._cache_dirty.add("monedas")
            self._schedule_flush()
            logger.info("Moneda creada: %s (%s) para usuario %d", nombre, abreviatura, usuario_id)
            return dict(nueva)

    def obtener_monedas(self, usuario_id: int) -> List[Dict[str, Any]]:
        monedas = self._cache.get("monedas", [])
        resultado = []
        for m in monedas:
            if int(m.get("usuario_id", 0)) == usuario_id:
                d = dict(m)
                d["es_default"] = bool(int(d.get("es_default", 0)))
                resultado.append(d)
        resultado.sort(key=lambda x: (not x.get("es_default", False), x.get("nombre", "")))
        return resultado

    def eliminar_moneda(self, usuario_id: int, moneda_id: int) -> bool:
        with LOCK:
            monedas = self._cache.get("monedas", [])
            nueva_lista = []
            eliminada = False
            for m in monedas:
                if int(m.get("id", 0)) == moneda_id and int(m.get("usuario_id", 0)) == usuario_id:
                    eliminada = True
                else:
                    nueva_lista.append(m)
            if eliminada:
                self._cache["monedas"] = nueva_lista
                self._cache_dirty.add("monedas")
                self._schedule_flush()
            return eliminada

    def establecer_moneda_default(self, usuario_id: int, moneda_id: int) -> bool:
        with LOCK:
            monedas = self._cache.get("monedas", [])
            actualizada = False
            for m in monedas:
                if int(m.get("usuario_id", 0)) == usuario_id:
                    if int(m.get("id", 0)) == moneda_id:
                        m["es_default"] = 1
                        actualizada = True
                    else:
                        m["es_default"] = 0
            if actualizada:
                self._cache_dirty.add("monedas")
                self._schedule_flush()
            return actualizada

    # ----------------------------------------------------------
    # NOTIFICACIONES
    # ----------------------------------------------------------

    def obtener_ultima_version_vista(self, usuario_id: int) -> Optional[str]:
        """Retorna la última versión de changelog que vio el usuario."""
        notifs = self._cache.get("notificaciones", [])
        usuario_notifs = [n for n in notifs if int(n.get("usuario_id", 0)) == usuario_id]
        if not usuario_notifs:
            return None
        usuario_notifs.sort(key=lambda x: int(x.get("id", 0)), reverse=True)
        return usuario_notifs[0].get("version")

    def registrar_notificacion(self, usuario_id: int, version: str):
        """Registra que el usuario vio una versión del changelog."""
        with LOCK:
            notifs = self._cache.get("notificaciones", [])
            nid = self._next_id("notificaciones")
            nueva = {
                "id": nid,
                "usuario_id": usuario_id,
                "version": version,
                "enviada_en": self._now(),
            }
            notifs.append(nueva)
            self._cache_dirty.add("notificaciones")
            self._schedule_flush()

    def contar_usuarios(self) -> int:
        """Retorna el total de usuarios registrados."""
        return len(self._cache.get("usuarios", []))

    def obtener_todos_los_usuarios(self) -> List[Dict[str, Any]]:
        """Retorna todos los usuarios registrados."""
        usuarios = self._cache.get("usuarios", [])
        return [{"id": u["id"], "telegram_user_id": u["telegram_user_id"], "nombre": u["nombre"]} for u in usuarios]

    # ----------------------------------------------------------
    # TABLAS (init compat)
    # ----------------------------------------------------------

    def crear_tablas(self):
        """Alias de init_sheets para compatibilidad con código existente."""
        self.init_sheets()


# ============================================================
# SINGLETON & FUNCIONES DE MÓDULO (misma interfaz que database.py)
# ============================================================

_db_instance: Optional[GoogleSheetsDB] = None


def _get_db() -> GoogleSheetsDB:
    """Retorna la instancia singleton, inicializándola si es necesario."""
    global _db_instance
    if _db_instance is None:
        _db_instance = GoogleSheetsDB()
    if not _db_instance._initialized:
        _db_instance.init_sheets()
    return _db_instance


def crear_tablas():
    _get_db().crear_tablas()


def obtener_o_crear_usuario(telegram_user_id: int, nombre: str) -> Dict[str, Any]:
    return _get_db().obtener_o_crear_usuario(telegram_user_id, nombre)


def obtener_usuario(telegram_user_id: int) -> Optional[Dict[str, Any]]:
    return _get_db().obtener_usuario(telegram_user_id)


def crear_categoria(usuario_id: int, nombre: str, tipo: str, descripcion: str = "", icono_color: str = "") -> Dict[str, Any]:
    return _get_db().crear_categoria(usuario_id, nombre, tipo, descripcion, icono_color)


def obtener_categorias(usuario_id: int, tipo: Optional[str] = None) -> List[Dict[str, Any]]:
    return _get_db().obtener_categorias(usuario_id, tipo)


def agregar_transaccion(usuario_id: int, categoria_id: int, tipo: str, cantidad: float, descripcion: str = "", moneda_id: Optional[int] = None) -> Dict[str, Any]:
    return _get_db().agregar_transaccion(usuario_id, categoria_id, tipo, cantidad, descripcion, moneda_id)


def obtener_transacciones(usuario_id: int, limite: int = 50, tipo: Optional[str] = None) -> List[Dict[str, Any]]:
    return _get_db().obtener_transacciones(usuario_id, limite, tipo)


def obtener_transacciones_por_fecha(usuario_id: int, fecha_inicio: str, fecha_fin: str,
                                     tipo: Optional[str] = None) -> List[Dict[str, Any]]:
    return _get_db().obtener_transacciones_por_fecha(usuario_id, fecha_inicio, fecha_fin, tipo)


def obtener_balance(usuario_id: int, fecha_inicio: Optional[str] = None) -> Dict[str, Any]:
    return _get_db().obtener_balance(usuario_id, fecha_inicio)


def obtener_presupuestos(usuario_id: int) -> List[Dict[str, Any]]:
    return _get_db().obtener_presupuestos(usuario_id)


def crear_presupuesto(usuario_id: int, categoria_id: int, cantidad_planejada: float, periodo: str, fecha_inicio: str, fecha_fin: Optional[str] = None) -> Dict[str, Any]:
    return _get_db().crear_presupuesto(usuario_id, categoria_id, cantidad_planejada, periodo, fecha_inicio, fecha_fin)


def obtener_metas_ahorro(usuario_id: int) -> List[Dict[str, Any]]:
    return _get_db().obtener_metas_ahorro(usuario_id)


def actualizar_meta_ahorro(meta_id: int, cantidad: float) -> bool:
    return _get_db().actualizar_meta_ahorro(meta_id, cantidad)


def contar_transacciones(usuario_id: int) -> Dict[str, Any]:
    return _get_db().contar_transacciones(usuario_id)


def flush_all():
    """Fuerza escritura de todas las hojas pendientes. Llamar al cerrar el bot."""
    try:
        _get_db().flush_all()
    except Exception as e:
        logger.error("Error en flush_all: %s", e)


def eliminar_transacciones(usuario_id: int) -> int:
    """Elimina todas las transacciones de un usuario. Retorna la cantidad eliminada."""
    with LOCK:
        db = _get_db()
        trans = db._cache.get("transacciones", [])
        eliminadas = 0
        nueva_lista = []
        for t in trans:
            if int(t.get("usuario_id", 0)) == usuario_id:
                eliminadas += 1
            else:
                nueva_lista.append(t)
        if eliminadas > 0:
            db._cache["transacciones"] = nueva_lista
            db._cache_dirty.add("transacciones")
            db._schedule_flush()
        return eliminadas


def obtener_transaccion_por_id(usuario_id: int, transaccion_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene una transacción específica por ID, verificando que pertenezca al usuario."""
    db = _get_db()
    trans = db._cache.get("transacciones", [])
    cats = db._cache.get("categorias", [])
    cat_lookup = {str(c["id"]): c for c in cats}

    for t in trans:
        if int(t.get("id", 0)) == transaccion_id and int(t.get("usuario_id", 0)) == usuario_id:
            row = dict(t)
            cat = cat_lookup.get(str(t.get("categoria_id", "")))
            if cat:
                row["categoria_nombre"] = cat.get("nombre", "")
                row["categoria_tipo"] = cat.get("tipo", "")
            else:
                row["categoria_nombre"] = ""
                row["categoria_tipo"] = ""
            return row
    return None


def actualizar_transaccion(usuario_id: int, transaccion_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Actualiza campos de una transacción. Campos soportados:
    tipo, cantidad, descripcion, categoria_id, fecha.
    Retorna la transacción actualizada o None si no se encontró.
    """
    with LOCK:
        db = _get_db()
        trans = db._cache.get("transacciones", [])

        campos_permitidos = {"tipo", "cantidad", "descripcion", "categoria_id", "fecha"}
        campos = {k: v for k, v in kwargs.items() if k in campos_permitidos and v is not None}

        if not campos:
            return None

        for t in trans:
            if int(t.get("id", 0)) == transaccion_id and int(t.get("usuario_id", 0)) == usuario_id:
                for k, v in campos.items():
                    t[k] = v
                db._cache_dirty.add("transacciones")
                db._schedule_flush()

                cats = db._cache.get("categorias", [])
                cat_lookup = {str(c["id"]): c for c in cats}
                row = dict(t)
                cat = cat_lookup.get(str(t.get("categoria_id", "")))
                if cat:
                    row["categoria_nombre"] = cat.get("nombre", "")
                    row["categoria_tipo"] = cat.get("tipo", "")
                else:
                    row["categoria_nombre"] = ""
                    row["categoria_tipo"] = ""
                return row
        return None


def eliminar_transaccion(usuario_id: int, transaccion_id: int) -> bool:
    """Elimina una transacción específica por ID. Retorna True si se eliminó."""
    with LOCK:
        db = _get_db()
        trans = db._cache.get("transacciones", [])
        nueva_lista = []
        eliminada = False
        for t in trans:
            if int(t.get("id", 0)) == transaccion_id and int(t.get("usuario_id", 0)) == usuario_id:
                eliminada = True
            else:
                nueva_lista.append(t)
        if eliminada:
            db._cache["transacciones"] = nueva_lista
            db._cache_dirty.add("transacciones")
            db._schedule_flush()
        return eliminada


def obtener_ultima_version_vista(usuario_id: int) -> Optional[str]:
    return _get_db().obtener_ultima_version_vista(usuario_id)


def registrar_notificacion(usuario_id: int, version: str):
    return _get_db().registrar_notificacion(usuario_id, version)


def contar_usuarios() -> int:
    return _get_db().contar_usuarios()


def obtener_todos_los_usuarios() -> List[Dict[str, Any]]:
    return _get_db().obtener_todos_los_usuarios()


def crear_moneda(usuario_id: int, nombre: str, simbolo: str, abreviatura: str, es_default: bool = False) -> Dict[str, Any]:
    return _get_db().crear_moneda(usuario_id, nombre, simbolo, abreviatura, es_default)


def obtener_monedas(usuario_id: int) -> List[Dict[str, Any]]:
    return _get_db().obtener_monedas(usuario_id)


def eliminar_moneda(usuario_id: int, moneda_id: int) -> bool:
    return _get_db().eliminar_moneda(usuario_id, moneda_id)


def establecer_moneda_default(usuario_id: int, moneda_id: int) -> bool:
    return _get_db().establecer_moneda_default(usuario_id, moneda_id)
