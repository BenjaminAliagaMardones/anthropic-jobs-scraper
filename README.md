# Anthropic Engineering Jobs Dashboard

Scraper en Python que extrae las ofertas de Engineering de Anthropic desde la API pública de Greenhouse, normaliza los datos (departamento, seniority, salario USD, ubicación, stack técnico vía regex curado) y los inyecta en un dashboard HTML estático auto-contenido.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

## Salidas

- `data/jobs_raw.json` — datos crudos normalizados
- `data/jobs.csv` — tabla normalizada
- `output/dashboard.html` — dashboard interactivo con los datos inyectados
- Resumen en consola
