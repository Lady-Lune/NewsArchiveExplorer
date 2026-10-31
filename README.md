# News Archive Explorer

News Archive Explorer is a small FastAPI web application for exploring topics discovered from a news archive with BERTopic.  
It presents topic sizes, trends over time, representative headlines, topic words, topic comparisons, and the model configuration used to create the export.

## Features

- Browse all discovered topics and sort them by size, name, or topic number.
- View a topic's headline count, corpus share, timeline, word cloud, and representative headlines.
- Filter headlines by topic-match strength and sort them by strength.
- Compare two topics on the same timeline and inspect their defining words.
- View the BERTopic model metadata and topic refinement flow.
- Expose the loaded data through JSON API endpoints.

## Requirements

- Python 3.10 or newer
- The JSON data files in `data/`

Install the Python dependencies in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the application

From the project directory, start the development server:

```bash
source .venv/bin/activate
uvicorn server:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser.

To run on all local interfaces or use another port:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

## Validate the data

The application expects `topics.json`, daily and monthly topic-frequency files, and one document file per topic. Validate the bundled export before starting the server:

```bash
python validate_data.py
```

Use a different data directory with `--data`, or treat warnings as failures with `--strict`:

```bash
python validate_data.py --data path/to/data
python validate_data.py --strict
```

See [DATA_VALIDATION.md](DATA_VALIDATION.md) for the complete data format and cross-file requirements.

## Pages

| URL | Description |
| --- | --- |
| `/` | Browse all topics |
| `/topic/{topic_id}` | Explore one topic |
| `/compare` | Compare two topics |
| `/model-info` | View model metadata and topic formation |

## API endpoints

| Endpoint | Description |
| --- | --- |
| `GET /api/topics` | Return all normalized topics |
| `GET /api/topics/{topic_id}/documents` | Return paginated topic documents with filtering and sorting |
| `GET /api/topics/{topic_id}/time_frequency` | Return daily or monthly topic frequency data |
| `GET /api/metadata` | Return corpus totals and model metadata |

## Project structure

```text
server.py             FastAPI application and routes
data_loader.py        JSON loading, normalization, and caching
validate_data.py      Export validation command
data/                 BERTopic export and document files
templates/            Jinja2 page templates
requirements.txt      Python dependencies
```
