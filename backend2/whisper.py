import os 
import torch 
import numpy as np
from typing import List, Tuple
import librosa
import tempfile

class WhisperTranscriber:
    def __init__(self, model_name: str = "base"):
        # don't import or load heavy libraries at module import time
        self.model_name = model_name
        self._model = None

        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Device: {self.device}")

    @staticmethod
    def load_audio(file_path: str, target_sampling_rate: int = 16000) -> Tuple[np.ndarray, int]:

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            audio, sr = librosa.load(file_path, sr=target_sampling_rate, mono= True)
            return(audio, sr)
        except Exception as e:
            raise Exception(f"Error loading audio file: {e}")
        
    @staticmethod
    def chunk_audio(audio: np.ndarray, chunk_length: int = 30, sampling_rate: int = 16000) -> List[np.ndarray]:
        chunk_size = chunk_length * sampling_rate
        return[audio[i+1:i+chunk_size] for i in range(0, len(audio), chunk_size)]
    
    def format_timestamp(self, seconds: int) -> str:
        """Convert seconds to HH:MM:SS format"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def transcribe_chunk(self, chunk: np.ndarray, sampling_rate: int = 16000) -> str:
        self._ensure_model()
        
        # OpenAI Whisper expects audio as a torch tensor or numpy array in float32
        # normalized to [-1, 1] range
        if chunk.dtype != np.float32:
            chunk = chunk.astype(np.float32)
        
        # Whisper internally expects 16kHz audio
        # Use fp16=False to avoid potential issues on CPU
        result = self._model.transcribe(
            chunk,
            language="en",
            task="transcribe",
            fp16=(self.device == 'cuda')  # Only use fp16 on CUDA
        )
        return result.get("text", "")
    
    def transcribe(self, file_path: str, chunk_length: int = 30) -> dict:
        """Transcribe audio file and return dict with time ranges as keys"""
        self._ensure_model()
        
        # For better results, transcribe the whole file at once
        # OpenAI Whisper handles chunking internally
        result = self._model.transcribe(
            file_path,
            language="en",
            task="transcribe",
            fp16=(self.device == 'cuda'),
            verbose=True  # Show progress
        )
        
        # Extract segments with timestamps
        transcriptions = {}
        if 'segments' in result:
            for segment in result['segments']:
                start_time = int(segment['start'])
                end_time = int(segment['end'])
                time_range = f"{self.format_timestamp(start_time)} - {self.format_timestamp(end_time)}"
                text = segment['text'].strip()
                if text:
                    transcriptions[time_range] = text
        else:
            # Fallback if no segments (shouldn't happen normally)
            transcriptions["00:00:00 - END"] = result.get("text", "").strip()
        
        return transcriptions
    
    def _ensure_model(self):
        if self._model is None:
            # import inside function so importing this module stays cheap
            import whisper
            # load_model will download/load weights; choose model_name per needs
            print(f"Loading Whisper model '{self.model_name}'...")
            self._model = whisper.load_model(self.model_name, device=self.device)
            print("Model loaded successfully!")
    
def main():
    try:
        # Initialize with a larger model for better accuracy
        transcriber = WhisperTranscriber(model_name='base')
        audio_file = "sample_audio.mp3"
        
        # Check if the file exists
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
        
        # Check if the file is empty
        if os.path.getsize(audio_file) == 0:
            raise ValueError(f"Audio file is empty: {audio_file}")
        
        transcriptions = transcriber.transcribe(audio_file, chunk_length=30)
        
        # Print transcriptions in time-ordered format
        for time_range, text in transcriptions.items():
            print(f'Timestamp: {time_range}')
            print(f'Transcription: {text}\n')
            
    except FileNotFoundError as e:
        print(f"File error: {e}")
    except ValueError as e:
        print(f"Invalid file error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()