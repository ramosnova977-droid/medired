-- =====================================================================
-- MEDIRED - Paso 2: inyectar más medicamentos (catálogo + inventario + historial)
-- =====================================================================
-- Agrega 71 medicamentos nuevos al catálogo, crea su inventario en las sedes
-- activas (≈85 % de las combinaciones; el resto queda "sin registro") y genera
-- ~15 movimientos por inventario en los últimos 35 días, para que los reportes
-- de movimientos tengan datos reales. Todo pasa por el trigger de trazabilidad.
--
-- * Es IDEMPOTENTE: si el medicamento ya existe (mismo nombre, forma y
--   concentración) no lo duplica, y si no hay medicamentos nuevos no inserta nada.
-- * También ARREGLA las secuencias (SERIAL): el seed original insertó ids a mano
--   y dejó los contadores en 1, lo que hacía fallar POST /api/medicamentos.
-- * Datos 100 % sintéticos (códigos CUM/IUM ficticios).
--
-- Ejecutar DESPUÉS de 01_reparar_codificacion.sql:
--   psql -U postgres -d medired -f database/02_seed_medicamentos_extra.sql
-- =====================================================================
SET client_encoding = 'UTF8';
SET search_path TO medired;
SELECT setseed(0.2026);

BEGIN;

-- 0) Reponer los contadores de todas las columnas SERIAL
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT table_name, column_name FROM information_schema.columns
           WHERE table_schema = 'medired' AND column_default LIKE 'nextval%'
  LOOP
    EXECUTE format(
      'SELECT setval(pg_get_serial_sequence(%L, %L), COALESCE((SELECT MAX(%I) FROM medired.%I), 1), (SELECT MAX(%I) IS NOT NULL FROM medired.%I))',
      'medired.' || r.table_name, r.column_name, r.column_name, r.table_name, r.column_name, r.table_name);
  END LOOP;
END $$;

-- 1) Catálogo: solo inserta lo que no exista
CREATE TEMP TABLE _nuevos (id_medicamento int) ON COMMIT DROP;

WITH v(nombre, principio, forma, conc, via, formula) AS (VALUES
  ('Naproxeno', 'Naproxeno sódico', 'Tableta', '250 mg', 'Oral', TRUE),
  ('Ácido acetilsalicílico', 'Ácido acetilsalicílico', 'Tableta', '100 mg', 'Oral', FALSE),
  ('Hidroclorotiazida', 'Hidroclorotiazida', 'Tableta', '25 mg', 'Oral', TRUE),
  ('Amlodipino', 'Amlodipino besilato', 'Tableta', '5 mg', 'Oral', TRUE),
  ('Carvedilol', 'Carvedilol', 'Tableta', '6.25 mg', 'Oral', TRUE),
  ('Espironolactona', 'Espironolactona', 'Tableta', '25 mg', 'Oral', TRUE),
  ('Captopril', 'Captopril', 'Tableta', '25 mg', 'Oral', TRUE),
  ('Metoprolol', 'Metoprolol tartrato', 'Tableta', '50 mg', 'Oral', TRUE),
  ('Atenolol', 'Atenolol', 'Tableta', '50 mg', 'Oral', TRUE),
  ('Simvastatina', 'Simvastatina', 'Tableta', '20 mg', 'Oral', TRUE),
  ('Glibenclamida', 'Glibenclamida', 'Tableta', '5 mg', 'Oral', TRUE),
  ('Insulina glargina', 'Insulina glargina', 'Solución inyectable', '100 UI/ml', 'Subcutánea', TRUE),
  ('Insulina cristalina', 'Insulina humana regular', 'Vial', '100 UI/ml', 'Subcutánea', TRUE),
  ('Sitagliptina', 'Sitagliptina', 'Tableta', '100 mg', 'Oral', TRUE),
  ('Pantoprazol', 'Pantoprazol sódico', 'Tableta', '40 mg', 'Oral', TRUE),
  ('Ciprofloxacino', 'Ciprofloxacino', 'Tableta', '500 mg', 'Oral', TRUE),
  ('Cefalexina', 'Cefalexina', 'Cápsula', '500 mg', 'Oral', TRUE),
  ('Claritromicina', 'Claritromicina', 'Tableta', '500 mg', 'Oral', TRUE),
  ('Trimetoprim sulfametoxazol', 'Trimetoprim / Sulfametoxazol', 'Tableta', '160 mg/800 mg', 'Oral', TRUE),
  ('Fluconazol', 'Fluconazol', 'Cápsula', '150 mg', 'Oral', TRUE),
  ('Aciclovir', 'Aciclovir', 'Tableta', '400 mg', 'Oral', TRUE),
  ('Ivermectina', 'Ivermectina', 'Tableta', '6 mg', 'Oral', TRUE),
  ('Albendazol', 'Albendazol', 'Tableta', '400 mg', 'Oral', FALSE),
  ('Cetirizina', 'Cetirizina', 'Tableta', '10 mg', 'Oral', FALSE),
  ('Dexametasona', 'Dexametasona', 'Tableta', '4 mg', 'Oral', TRUE),
  ('Budesonida', 'Budesonida', 'Inhalador', '200 mcg/dosis', 'Inhalada', TRUE),
  ('Bromuro de ipratropio', 'Ipratropio bromuro', 'Inhalador', '20 mcg/dosis', 'Inhalada', TRUE),
  ('Montelukast', 'Montelukast sódico', 'Tableta', '10 mg', 'Oral', TRUE),
  ('Sertralina', 'Sertralina', 'Tableta', '50 mg', 'Oral', TRUE),
  ('Fluoxetina', 'Fluoxetina', 'Cápsula', '20 mg', 'Oral', TRUE),
  ('Amitriptilina', 'Amitriptilina', 'Tableta', '25 mg', 'Oral', TRUE),
  ('Carbamazepina', 'Carbamazepina', 'Tableta', '200 mg', 'Oral', TRUE),
  ('Ácido valproico', 'Ácido valproico', 'Cápsula', '250 mg', 'Oral', TRUE),
  ('Levetiracetam', 'Levetiracetam', 'Tableta', '500 mg', 'Oral', TRUE),
  ('Risperidona', 'Risperidona', 'Tableta', '2 mg', 'Oral', TRUE),
  ('Haloperidol', 'Haloperidol', 'Tableta', '5 mg', 'Oral', TRUE),
  ('Tramadol', 'Tramadol clorhidrato', 'Cápsula', '50 mg', 'Oral', TRUE),
  ('Morfina', 'Morfina sulfato', 'Solución inyectable', '10 mg/ml', 'Intravenosa', TRUE),
  ('Metoclopramida', 'Metoclopramida', 'Tableta', '10 mg', 'Oral', TRUE),
  ('Loperamida', 'Loperamida', 'Cápsula', '2 mg', 'Oral', FALSE),
  ('Sales de rehidratación oral', 'Sales de rehidratación oral', 'Polvo', '27.9 g', 'Oral', FALSE),
  ('Sulfato ferroso', 'Sulfato ferroso', 'Tableta', '300 mg', 'Oral', FALSE),
  ('Carbonato de calcio + vitamina D', 'Calcio / Colecalciferol', 'Tableta', '600 mg/400 UI', 'Oral', FALSE),
  ('Hidrocortisona', 'Hidrocortisona', 'Crema', '1 %', 'Tópica', FALSE),
  ('Clotrimazol', 'Clotrimazol', 'Crema', '1 %', 'Tópica', FALSE),
  ('Povidona yodada', 'Povidona yodada', 'Solución', '10 %', 'Tópica', FALSE),
  ('Cloruro de sodio', 'Cloruro de sodio', 'Solución inyectable', '0.9 %', 'Intravenosa', TRUE),
  ('Acetaminofén', 'Acetaminofén', 'Jarabe', '150 mg/5 ml', 'Oral', FALSE),
  ('Ibuprofeno', 'Ibuprofeno', 'Suspensión oral', '100 mg/5 ml', 'Oral', FALSE),
  ('Lactulosa', 'Lactulosa', 'Jarabe', '667 mg/ml', 'Oral', FALSE),
  ('Butilbromuro de hioscina', 'Hioscina butilbromuro', 'Tableta', '10 mg', 'Oral', FALSE),
  ('Dimenhidrinato', 'Dimenhidrinato', 'Tableta', '50 mg', 'Oral', FALSE),
  ('Clopidogrel', 'Clopidogrel', 'Tableta', '75 mg', 'Oral', TRUE),
  ('Enoxaparina', 'Enoxaparina sódica', 'Jeringa prellenada', '40 mg/0.4 ml', 'Subcutánea', TRUE),
  ('Tamsulosina', 'Tamsulosina', 'Cápsula', '0.4 mg', 'Oral', TRUE),
  ('Finasterida', 'Finasterida', 'Tableta', '5 mg', 'Oral', TRUE),
  ('Levonorgestrel + etinilestradiol', 'Levonorgestrel / Etinilestradiol', 'Tableta', '0.15 mg/0.03 mg', 'Oral', TRUE),
  ('Medroxiprogesterona', 'Medroxiprogesterona acetato', 'Solución inyectable', '150 mg/ml', 'Intramuscular', TRUE),
  ('Rivaroxabán', 'Rivaroxabán', 'Tableta', '20 mg', 'Oral', TRUE),
  ('Digoxina', 'Digoxina', 'Tableta', '0.25 mg', 'Oral', TRUE),
  ('Isosorbida dinitrato', 'Isosorbida dinitrato', 'Tableta', '10 mg', 'Oral', TRUE),
  ('Gabapentina', 'Gabapentina', 'Cápsula', '300 mg', 'Oral', TRUE),
  ('Pregabalina', 'Pregabalina', 'Cápsula', '75 mg', 'Oral', TRUE),
  ('Sucralfato', 'Sucralfato', 'Tableta', '1 g', 'Oral', TRUE),
  ('Ceftriaxona', 'Ceftriaxona sódica', 'Polvo para inyección', '1 g', 'Intravenosa', TRUE),
  ('Gentamicina', 'Gentamicina', 'Solución inyectable', '80 mg/2 ml', 'Intramuscular', TRUE),
  ('Penicilina benzatínica', 'Bencilpenicilina benzatínica', 'Polvo para inyección', '1.200.000 UI', 'Intramuscular', TRUE),
  ('Prednisona', 'Prednisona', 'Tableta', '20 mg', 'Oral', TRUE),
  ('Metimazol', 'Metimazol', 'Tableta', '5 mg', 'Oral', TRUE),
  ('Alopurinol', 'Alopurinol', 'Tableta', '300 mg', 'Oral', TRUE),
  ('Colchicina', 'Colchicina', 'Tableta', '0.5 mg', 'Oral', TRUE)
), ins AS (
  INSERT INTO medicamento (nombre, principio_activo, forma_farmaceutica, concentracion, via_administracion, requiere_formula)
  SELECT v.nombre, v.principio, v.forma, v.conc, v.via, v.formula FROM v
  WHERE NOT EXISTS (
    SELECT 1 FROM medicamento m
    WHERE lower(m.nombre) = lower(v.nombre) AND m.forma_farmaceutica = v.forma
      AND COALESCE(m.concentracion, '') = v.conc)
  RETURNING id_medicamento
)
INSERT INTO _nuevos SELECT id_medicamento FROM ins;

UPDATE medicamento m
   SET codigo_cum = 'CUM-' || (20000000 + m.id_medicamento) || '-1',
       codigo_ium = 'IUM-' || (300000 + m.id_medicamento)
 WHERE m.id_medicamento IN (SELECT id_medicamento FROM _nuevos) AND m.codigo_cum IS NULL;

-- 2) Inventario por sede (qty 0; las existencias entran como movimientos)
INSERT INTO inventario (id_medicamento, id_sede, cantidad_disponible, cantidad_reservada, stock_minimo)
SELECT n.id_medicamento, s.id_sede, 0, 0, (ARRAY[10,15,20,25,30,40,50,60,80])[1 + floor(random() * 9)::int]
FROM _nuevos n CROSS JOIN sede s
WHERE s.activo AND random() < 0.85;

-- 3) Plan de existencias: ~62 % disponible, 15 % bajo, 15 % crítico, 8 % agotado
CREATE TEMP TABLE _plan ON COMMIT DROP AS
SELECT i.id_inventario, i.stock_minimo AS mn,
       random() AS rc, random() AS ra, random() AS rb, random() AS rd, random() AS re,
       0 AS fin, 0 AS e1, 0 AS e2, 0 AS e3, 0 AS s
FROM inventario i WHERE i.id_medicamento IN (SELECT id_medicamento FROM _nuevos);

UPDATE _plan SET fin = CASE
    WHEN rc < 0.08 THEN 0
    WHEN rc < 0.23 THEN floor(mn * ra * 0.95)::int
    WHEN rc < 0.38 THEN mn + floor(mn * ra)::int
    ELSE 2 * mn + floor(mn * (0.2 + ra * 5))::int END;
UPDATE _plan SET e1 = fin + floor(mn * (1 + rb * 2))::int + 5,
                 e2 = floor(mn * (0.5 + rd * 1.5))::int,
                 e3 = floor(mn * re)::int + 1;
UPDATE _plan SET s = e1 + e2 + e3 - fin;

-- 4) Movimientos cronológicos (el trigger calcula stock_anterior / stock_nuevo)
INSERT INTO movimiento_inventario (id_inventario, tipo_movimiento, cantidad, stock_anterior, stock_nuevo, id_operador, fuente, fecha_hora)
SELECT m.id_inventario, m.tipo, m.cant, 0, 0,
       (SELECT id_usuario FROM usuario WHERE rol = 'operador_inventario' ORDER BY id_usuario LIMIT 1),
       m.fuente,
       date_trunc('day', now()) - m.dias * interval '1 day' + (8 + floor(random() * 9)) * interval '1 hour'
FROM (
  SELECT id_inventario, 'entrada' AS tipo, e1 AS cant, 'carga_inicial' AS fuente, 35 AS dias FROM _plan
  UNION ALL SELECT id_inventario, 'entrada', e2, 'reposicion', 28 FROM _plan
  UNION ALL SELECT id_inventario, 'entrada', e3, 'reposicion', 21 FROM _plan
  UNION ALL SELECT p.id_inventario, 'salida',
         CASE v.k WHEN 12 THEN p.s - 11 * (p.s / 12) ELSE p.s / 12 END, 'dispensacion',
         (1 + floor(random() * 19))::int
    FROM _plan p, generate_series(1, 12) AS v(k)
) m
ORDER BY m.dias DESC, m.id_inventario, random();

UPDATE inventario i
   SET fecha_actualizacion = COALESCE((SELECT max(fecha_hora) FROM movimiento_inventario x WHERE x.id_inventario = i.id_inventario), i.fecha_actualizacion)
 WHERE i.id_inventario IN (SELECT id_inventario FROM _plan);

COMMIT;

-- Resumen
SELECT (SELECT count(*) FROM medicamento) AS medicamentos,
       (SELECT count(*) FROM inventario)  AS registros_inventario,
       (SELECT count(*) FROM movimiento_inventario) AS movimientos;
