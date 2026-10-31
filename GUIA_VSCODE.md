# MEDIRED · Guía para poner las mejoras en tu VS Code

Qué trae este paquete: tildes reparadas, +71 medicamentos con inventario e historial, página nueva
(Medicamentos, Sedes, Inventario, Disponibilidad, **Reportes con gráficos**), **registro / inicio de sesión / mi cuenta**
y los endpoints nuevos del backend.

> Antes de empezar, haz una copia de tu carpeta `medired` (por si quieres volver atrás).

## 1. Copiar los archivos
Extrae el zip **encima** de tu proyecto (acepta reemplazar). Queda así:

```
medired/
├─ .env.example                       (nuevo: plantilla, tu .env NO se toca)
├─ GUIA_VSCODE.md                     (este archivo)
├─ backend/
│  ├─ app.py                          (cambia)  registra las rutas nuevas
│  ├─ config.py                       (cambia)  clave de sesión
│  ├─ schemas.py                      (cambia)  esquemas de registro/login
│  ├─ security.py                     (NUEVO)   contraseñas, tokens, roles
│  ├─ crear_usuario.py                (NUEVO)   crea administrador/operador desde terminal
│  └─ routes/
│     ├─ auth.py                      (NUEVO)   registro, login, perfil, usuarios
│     ├─ reportes.py                  (NUEVO)   datos de los reportes
│     ├─ inventario.py                (cambia)  GET /api/inventario + entradas/salidas con sesión
│     └─ medicamentos.py              (cambia)  crear medicamento requiere operador/admin
├─ database/
│  ├─ 01_reparar_codificacion.sql     (NUEVO)   arregla "EngativÃ¡" → "Engativá"
│  └─ 02_seed_medicamentos_extra.sql  (NUEVO)   +71 medicamentos, inventario e historial
└─ frontend/index.html                (REEMPLAZA la página completa)
```

## 2. Base de datos (pgAdmin)
1. Abre pgAdmin → base `medired` → clic derecho → **Query Tool**.
2. Botón de abrir archivo (📂) → `database/01_reparar_codificacion.sql` → **F5**.
   La consulta final debe devolver **0 filas** (ya no quedan `Ã`).
3. Abre `database/02_seed_medicamentos_extra.sql` → **F5**.
   Al final muestra: medicamentos = 91, registros_inventario ≈ 950, movimientos ≈ 11.890.
4. Los dos scripts se pueden ejecutar de nuevo sin duplicar nada.

> Por qué salían las tildes mal: el seed (UTF-8) se cargó con el cliente en WIN1252.
> Si vuelves a cargar un `.sql` por terminal: `psql -U postgres -d medired -f archivo.sql` con `set PGCLIENTENCODING=UTF8`
> (PowerShell: `$env:PGCLIENTENCODING="UTF8"`). Los scripts nuevos ya incluyen `SET client_encoding = 'UTF8'`.

## 3. Configuración (.env)
Abre tu `.env` y **agrega** una línea con una clave larga inventada por ti (no cambies lo demás):
```
MEDIRED_SECRET_KEY=pon-aqui-una-frase-larga-y-aleatoria-de-40-caracteres
```
(Si no la pones, funciona con una clave de desarrollo, pero cámbiala antes de mostrarlo en serio.)

## 4. Backend (terminal de VS Code: Ctrl + ñ)
```powershell
cd backend
venv\Scripts\activate            # si PowerShell bloquea: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt  # no hay dependencias nuevas, pero por si acaso
python crear_usuario.py --demo   # crea cuentas de prueba (ver abajo)
uvicorn app:app --reload
```

## 5. Probar
Abre **http://localhost:8000/pagina**. Arriba a la izquierda del chip debe decir **"En vivo"**
(si dice "Demostración", la API no está corriendo o abriste el archivo con doble clic).

| Qué probar | Cómo |
|---|---|
| Inventario | menú **Inventario**: tabla filtrable, ordenable, exporta CSV |
| Reportes de inventario | menú **Reportes** → pestaña Inventario (gráficos, CSV, Imprimir/PDF) |
| Reportes de movimientos | inicia sesión con `analista@medired.test` → pestaña Movimientos |
| Registro de pacientes | **Crear cuenta** (arriba a la derecha) |
| Registrar entradas/salidas | sesión `operador@medired.test` → botón **±** en Inventario o en un medicamento |
| Administrar usuarios | sesión `admin@medired.test` → **Mi cuenta** → tabla de usuarios (cambiar rol) |

Cuentas demo (contraseña **Medired2026**): `admin@medired.test`, `operador@medired.test`, `analista@medired.test`.
Son públicas: úsalas solo en desarrollo. Para un administrador real:
```powershell
python crear_usuario.py --rol administrador --documento 1020304050 --nombre "Tu Nombre" --email tu@correo.com
```

## 6. Reglas de acceso
- Cualquiera puede consultar medicamentos, sedes e inventario.
- Quien se registra queda como **paciente** (guarda favoritos). Nadie puede auto-asignarse otro rol.
- **Operador de inventario / administrador:** registran entradas y salidas, crean medicamentos.
- **Analista / operador / administrador:** ven el reporte de movimientos.
- **Administrador:** además cambia roles y activa/desactiva usuarios.

## 7. Si algo falla
| Síntoma | Causa y arreglo |
|---|---|
| Banner amarillo "No se pudo conectar" | La API no está corriendo, o abriste `index.html` directo. Usa `uvicorn` y entra por `/pagina`. |
| Tildes aún dañadas | Ejecuta el script 01 otra vez; refresca con Ctrl+F5. (La página también repara textos dañados al mostrarlos.) |
| 401 "Sesión no válida" | Tu sesión expiró (12 h) o cambiaste `MEDIRED_SECRET_KEY`: vuelve a ingresar. |
| 403 al registrar entrada | Tu rol es paciente/analista: entra con operador o administrador. |
| `ModuleNotFoundError` | No activaste el venv: `venv\Scripts\activate`. |
| Puerto 8000 ocupado | `uvicorn app:app --reload --port 8001` y abre `localhost:8001/pagina`. |
| "Ya existe una cuenta con ese correo/documento" | Esa persona ya se registró: usa Ingresar. |

## 8. Cuidados
- No subas el `.env` a GitHub (tiene tu contraseña de Postgres): añade `.env` a un `.gitignore` en la raíz.
- Los datos son sintéticos; si vas a manejar datos reales de pacientes aplica la Ley 1581 de 2012 y pon HTTPS.
