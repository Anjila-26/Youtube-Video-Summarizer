# Youtube Video Summarizer — Backend

This backend provides the core processing for the Youtube Video Summarizer app: downloading videos, extracting audio, transcribing using Whisper, creating embeddings and storing/retrieving them with ChromaDB, and serving endpoints via FastAPI.

## Repository layout (relevant files)

- `api.py` — FastAPI app exposing endpoints to upload/process videos and query summaries.
- `mp4_downloader.py` — Utility to download YouTube videos (uses `yt-dlp` / `pytube`).
- `whisper.py` — Audio transcription helpers (integrates OpenAI/Whisper models).
- `vector_store.py` — Code to build and query the ChromaDB vector store.
- `Model/` — Local LLM model file (e.g. `Phi-3.5-mini-instruct-*.gguf`).
- `chroma_db/` — Local ChromaDB storage (SQLite + index files).
- `Saved_Media/` — Downloaded video/audio files.
- `requirements.txt` — Python dependencies for the backend.

## Prerequisites

- Python 3.10+ (recommend 3.11)
- `ffmpeg` installed and available on `PATH`
- Enough disk space for downloaded videos and model files
- If using local LLMs: sufficient CPU/RAM and (optionally) GPU drivers

On Windows you can install `ffmpeg` via Chocolatey or download from ffmpeg.org.

## Setup (recommended)

1. Create and activate a virtual environment (conda or venv). Example with conda:

```powershell
conda create -n yt_summarizer python=3.11 -y
conda activate yt_summarizer
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Ensure `ffmpeg` is reachable:

```powershell
ffmpeg -version
```

4. Place your local model in `Model/` (if using local LLM). Example: `Model/Phi-3.5-mini-instruct-Q4_K_L.gguf`.

	Go to this link to download the model file (Hugging Face):

	https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_L.gguf?download=true

## Environment variables

Create a `.env` file in `backend2/` if you need to override defaults. Typical entries:

```
# .env example
CHROMA_DB_PATH=./chroma_db/chroma.sqlite3
MODEL_PATH=./Model/Phi-3.5-mini-instruct-Q4_K_L.gguf
```

`python-dotenv` is used by the code to read `.env` values.

## Running the API (development)

From the `backend2` directory run:

```powershell
# start uvicorn server
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

The OpenAPI docs will be available at `http://localhost:8000/docs`.

## Using the tools

- Download a video:

```powershell
python mp4_downloader.py --url "<youtube-url>" --outdir Saved_Media/
```

- Transcribe an audio/video file (example functions in `whisper.py`):

```powershell
python -c "from whisper import transcribe_file; print(transcribe_file('Saved_Media/video.mp4'))"
```

- Build or update the vector store (see `vector_store.py`):

```powershell
python vector_store.py --build --media-dir Saved_Media/
```

Replace flags with the actual arguments in the script; see each file's docstrings for details.

## Notes about models and ChromaDB

- ChromaDB files live under `chroma_db/`. Back these up if you reindex or move machines.
- If you use a large local LLM, ensure `Model/` contains the right `.gguf` or model artifacts and the code points to it via `MODEL_PATH`.

## Troubleshooting

- Permission errors when pushing to GitHub: ensure Git credentials and remote match the intended account.
- `ffmpeg` errors: confirm `ffmpeg` binary is installed and in `PATH`.
- `torchaudio`/`torch` install issues: prefer installing `torch`/`torchaudio` from the official wheel instructions for your CUDA/CPU environment.

## Development tips

- Use the included `requirements.txt` at repository root to mirror backend dependencies.
- Run the FastAPI server locally and test endpoints via `http://localhost:8000/docs`.

## License & Attribution

This project reuses open-source components (Whisper, LangChain, ChromaDB, etc.). Check each dependency's license for redistribution requirements.
