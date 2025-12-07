# Youtube Video Summarizer

A small project that downloads YouTube videos, transcribes audio with Whisper, indexes embeddings with ChromaDB, and serves a summarization API. The repository contains a Next.js frontend and a Python backend that performs download, transcription, embedding, and retrieval.

## Structure

- `app/` — Next.js frontend (see `app/README.md`).
- `backend2/` — Python backend (FastAPI) which handles downloading, transcription, and vector store (see `backend2/README.md`).

## Model download

If you use the included local LLM, download the GGUF model and place it in `backend2/Model/` (or adjust `MODEL_PATH` in `.env`):

https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_L.gguf?download=true

## Quick start

1. Create & activate Python environment (recommended: conda):

```powershell
conda create -n yt_summarizer python=3.11 -y
conda activate yt_summarizer
```

2. Install backend dependencies (from repo root):

```powershell
pip install -r requirements.txt
```

3. Ensure `ffmpeg` is installed and on `PATH`:

```powershell
ffmpeg -version
```

4. Run the backend (from `backend2/`):

```powershell
cd backend2
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

5. Run the frontend (from `app/`):

```bash
cd app
npm install
npm run dev
```

Open the frontend at `http://localhost:3000` and the backend docs at `http://localhost:8000/docs`.

## Notes

- If you plan to use local LLMs, place the model file in `backend2/Model/` and update `backend2/.env` (`MODEL_PATH`) if needed.
- Use `Saved_Media/` (under `backend2`) to keep downloaded videos/audio.
- See `backend2/README.md` for detailed backend instructions and the model link.

