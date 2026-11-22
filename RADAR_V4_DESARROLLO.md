# Radar Compra Ágil Salud — desarrollo V4

Esta rama es de **desarrollo**, no de producción. El dashboard público de Streamlit
sigue usando los CSV originales de la raíz de `main`.

## Arquitectura provisional

- `scripts/actualizar_radar_v4.py`: consulta la API y guarda **solo** en
  `staging_radar_v4/` los archivos `clasificacion_v4.csv`, `auditoria_v4.csv`,
  `reporte_v4.json` y `detalles_crudos_v4.jsonl`.
- `scripts/reclasificar_radar_v4.py`: reutiliza capturas de detalles de la API para
  clasificar nuevamente sin red, sin ticket y sin descargar datos repetidos.
- `scripts/probar_clasificador_v4.py`: casos sintéticos de regresión,
  reintentos HTTP simulados y prueba de reclasificación sin API.
- `.github/workflows/radar-v4-pruebas.yml`: ejecuta automáticamente estas
  pruebas cuando cambia la rama o el Pull Request.

## Ejecutar localmente (sin API)

```bash
python -m pip install "requests>=2.31,<3"
python scripts/probar_clasificador_v4.py
```

## Reclasificar capturas previas (sin API)

```bash
python scripts/reclasificar_radar_v4.py staging_radar_v4/detalles_crudos_v4.jsonl
```

Las capturas se generan en futuras ejecuciones de la ingesta V4. No se incluyen
credenciales ni datos de autenticación en ellas. **No subir las capturas ni los
resultados de staging a producción sin revisión previa.**

## Limitaciones y criterios de salida

- La heurística sigue siendo provisional: no es una transcripción exacta de
  Apps Script V3.8.1; no procesa adjuntos, ofertas ni adjudicaciones.
- Las pruebas sintéticas no reemplazan la validación de oportunidades reales.
- El extractor consulta un número configurable de páginas por término. Una
  ejecución completa dentro de ese alcance **no implica cobertura exhaustiva
  del universo de Compra Ágil**.
- La API puede devolver errores 504. Ante errores persistentes, se registra el
  fallo y se bloquea la publicación; nunca se deben reemplazar CSV válidos
  por resultados incompletos.
- No hay publicación automática ni cron de seis horas habilitados todavía.
  Se activarán únicamente después de comprobar integridad, deduplicación,
  compatibilidad con Streamlit y reglas de clasificación.
