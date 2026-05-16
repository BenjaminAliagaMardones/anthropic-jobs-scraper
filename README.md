# Anthropic Jobs Scraper & Analyzer

Scrapea ofertas de Engineering desde la API pública de Greenhouse de Anthropic, extrae tecnologías con Gemini (Google AI) y genera estadísticas + gráficos.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edita .env y pega tu GEMINI_API_KEY (https://aistudio.google.com/apikey)
```

## Uso

```bash
python main.py            # pipeline completo
python main.py --no-llm   # solo regex (sin Gemini)
python main.py --reuse    # usa data/jobs_raw.json si existe (no re-scrapea)
```

## Salidas

- `data/jobs_raw.json` — datos crudos
- `data/jobs.csv` — tabla normalizada
- `output/*.png` — gráficos estáticos
- `output/locations_map.html` — mapa interactivo
- Resumen en consola
