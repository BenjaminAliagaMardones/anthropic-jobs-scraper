# Anthropic Engineering Jobs Dashboard

Scraper que extrae las ofertas de Engineering de Anthropic desde la API pública de Greenhouse y las renderiza en un dashboard HTML estático.

**Live:** https://benjaminaliagamardones.github.io/anthropic-jobs-scraper/

## Tecnologías

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?logo=pandas&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

El dashboard generado queda en `output/dashboard.html`.

## Despliegue

Un workflow de GitHub Actions regenera el dashboard cada día.
