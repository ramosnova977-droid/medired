-- =====================================================================
-- MEDIRED - Paso 1: reparar tildes dañadas ("EngativÃ¡" -> "Engativá")
-- =====================================================================
-- Causa: el seed (UTF-8) se cargó con el cliente en WIN1252/LATIN1 (pasa en
-- Windows con pgAdmin o psql). Cada tilde quedó guardada como 2 caracteres.
-- Este script revierte ese error. Es SEGURO ejecutarlo varias veces:
-- solo toca textos que contienen los caracteres típicos del daño (Ã, Â).
--
-- Cómo ejecutarlo (pgAdmin): abre este archivo en Query Tool y presiona F5.
-- Cómo ejecutarlo (terminal):
--   psql -U postgres -d medired -f database/01_reparar_codificacion.sql
-- =====================================================================
SET client_encoding = 'UTF8';
SET search_path TO medired;

CREATE OR REPLACE FUNCTION fn_reparar_utf8(t text) RETURNS text AS $$
DECLARE
    r text;
BEGIN
    IF t IS NULL OR t !~ '[ÃÂï]' THEN
        RETURN t;
    END IF;
    BEGIN
        r := convert_from(convert_to(t, 'WIN1252'), 'UTF8');
        RETURN r;
    EXCEPTION WHEN others THEN NULL;
    END;
    BEGIN
        r := convert_from(convert_to(t, 'LATIN1'), 'UTF8');
        RETURN r;
    EXCEPTION WHEN others THEN NULL;
    END;
    RETURN t;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

UPDATE sede SET nombre = fn_reparar_utf8(nombre), localidad = fn_reparar_utf8(localidad),
                direccion = fn_reparar_utf8(direccion), horario = fn_reparar_utf8(horario);
UPDATE medicamento SET nombre = fn_reparar_utf8(nombre), principio_activo = fn_reparar_utf8(principio_activo),
                forma_farmaceutica = fn_reparar_utf8(forma_farmaceutica),
                concentracion = fn_reparar_utf8(concentracion), via_administracion = fn_reparar_utf8(via_administracion);
UPDATE usuario SET nombre = fn_reparar_utf8(nombre), email = fn_reparar_utf8(email);
UPDATE eps SET nombre = fn_reparar_utf8(nombre);
UPDATE entrega SET direccion_entrega = fn_reparar_utf8(direccion_entrega), transportista = fn_reparar_utf8(transportista);

-- Caso especial: en "seed synthetic corregido.sql" la Á de "Ácido fólico" se perdió del todo.
UPDATE medicamento
   SET nombre = 'Ácido fólico', principio_activo = 'Ácido fólico'
 WHERE codigo_cum = 'CUM-20000018-1' AND nombre !~ '^Ácido';

DROP FUNCTION fn_reparar_utf8(text);

-- Verificación: no debería devolver filas con Ã ni Â
SELECT 'sede' AS tabla, nombre FROM sede WHERE nombre ~ '[ÃÂ]'
UNION ALL SELECT 'medicamento', nombre FROM medicamento WHERE nombre ~ '[ÃÂ]';
