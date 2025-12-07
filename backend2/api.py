from fastapi import FastAPI, HTTPException
from mp4_downloader import *
from pydantic import BaseModel, validator
from typing import Dict, Tuple
import re
from vector_store import VideoVectorStore

from typing import List, Dict, Any
#Langchain imports
from langchain_community.llms import Ollama
from langchain_core.callbacks import CallbackManager, StreamingStdOutCallbackHandler
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.summarize import load_summarize_chain
from langchain.text_splitter import TokenTextSplitter
from langchain.schema import Document

import os
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with specific domains to restrict access if needed
    allow_credentials=True,
    allow_methods=["*"],  # Allow specific HTTP methods or all
    allow_headers=["*"],  # Allow specific headers or all
)

class VideoRequest(BaseModel):
    youtube_video_url: str

    @validator('youtube_video_url')
    def validate_youtube_url(cls, v):
        youtube_pattern = r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+(\S*)?$'
        if not re.match(youtube_pattern, v):
            raise ValueError('Invalid YouTube URL')
        return v
    
def initialize_llm():
    callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])
    return Ollama(base_url="http://localhost:11434", model="quantphi", callback_manager=callback_manager)

llm = initialize_llm()
text_splitter = TokenTextSplitter(chunk_size=10000, chunk_overlap=200)

map_template = """<|system|>
You are an AI assistant specialized in understanding and concisely describing video content.
<|end|>
<|user|>
Please describe the main ideas in the following content:
{text}
Provide a brief description of the key points.
<|end|>
<|assistant|>
"""
map_prompt = ChatPromptTemplate.from_template(map_template)

refine_template = """<|system|>
You are an AI assistant specialized in creating concise descriptions of video content.
<|end|>
<|user|>
Here's what we know about a video so far:
{existing_answer}
We have some new information to add:
{text}
Please incorporate this new information and create a single, concise paragraph that captures the main ideas of the entire video. Follow these guidelines:

1. Focus on the most important information and key takeaways.
2. Keep the paragraph brief, ideally 3-4 sentences.
3. Present the information directly without mentioning that it's from a video or a description.
4. Write in a clear, straightforward style.
5. Avoid using meta-language or referring to the writing process.

<|end|>
<|assistant|>
"""
refine_prompt = ChatPromptTemplate.from_template(refine_template)
summarize_chain = load_summarize_chain(
    llm,
    chain_type="refine",
    question_prompt=map_prompt,
    refine_prompt=refine_prompt,
    return_intermediate_steps=True,
    input_key="input_documents",
    output_key="output_text",
    verbose=True
)

def summarize_transcript(transcript):
    chunks = text_splitter.split_text(transcript)
    docs = [Document(page_content=chunk) for chunk in chunks]
    result = summarize_chain({"input_documents": docs})
    return result["output_text"]

def get_text_from_subtitles(subtitle_dict: Dict[str, str]) -> str:
    """Extract only text content from subtitle dictionary"""
    try:
        if not subtitle_dict:
            return ""
        if isinstance(subtitle_dict, dict):
            # Join all text values from the dictionary
            return " ".join(str(text) if isinstance(text, str) else 
                          text[0]['text'] if isinstance(text, list) else str(text) 
                          for text in subtitle_dict.values())
        elif isinstance(subtitle_dict, str):
            return subtitle_dict
        else:
            print(f"Debug - unexpected subtitle_dict type: {type(subtitle_dict)}")
            return str(subtitle_dict)
    except Exception as e:
        print(f"Debug - Error in get_text_from_subtitles: {str(e)}")
        raise

async def get_transcription(video_url: str) -> Tuple[Dict[str, str], bool, str]:
    """Get transcription either from subtitles or Whisper and return with source info"""
    try:
        # Try getting subtitles first
        print("Debug - Fetching subtitles...")
        subtitle_dict = extract_subtitles(video_url)
    
        if subtitle_dict:
            print("Using YouTube subtitles")
            grouped_subtitles = group_subtitles_by_interval(subtitle_dict)
            text_content = get_text_from_subtitles(grouped_subtitles)
            summary = summarize_transcript(text_content)
            formatted_subtitles = {}
            for time_range, text in grouped_subtitles.items():
                start_time = time_range.split(' - ')[0]
                seconds = sum(float(x) * 60 ** i for i, x in enumerate(reversed(start_time.split(':'))))
                formatted_subtitles[time_range] = [{
                    'start': seconds,
                    'text': text,
                    'display_time': start_time
                }]
            return formatted_subtitles, True, summary
        
        # Download and process video if no subtitles available
        print("No subtitles found, using Whisper transcription")
        try:
            process_youtube_video(video_url)
            transcriber = get_transcriber()
            audio_path = os.path.join('Saved_Media', 'audio.mp3')
            if not os.path.exists(audio_path):
                raise FileNotFoundError("Audio file not found")
            
            transcription = transcriber.transcribe(audio_path)
            formatted_transcription = {}
            
            if isinstance(transcription, dict):
                for time_range, text in transcription.items():
                    try:
                        # Parse the time range string (e.g., "00:00:30 - 00:01:00")
                        start_time = time_range.split(' - ')[0]
                        end_time = time_range.split(' - ')[1]
                        
                        # Convert start time to seconds
                        h, m, s = map(float, start_time.split(':'))
                        start_seconds = h * 3600 + m * 60 + s
                        
                        formatted_transcription[time_range] = [{
                            'start': start_seconds,
                            'text': str(text),
                            'display_time': start_time
                        }]
                    except Exception as e:
                        print(f"Error parsing time range {time_range}: {e}")
                        continue
            else:
                # For non-dict transcriptions, try to extract timestamp from the data
                try:
                    import re
                    timestamp_pattern = r'(\d{2}):(\d{2}):(\d{2})'
                    matches = re.findall(timestamp_pattern, str(transcription))
                    if matches:
                        start_time = matches[0]
                        seconds = int(start_time[0]) * 3600 + int(start_time[1]) * 60 + int(start_time[2])
                    else:
                        seconds = 0
                        
                    formatted_transcription = {"00:00:00 - 00:00:30": [{
                        'start': seconds,
                        'text': str(transcription),
                        'display_time': f"{int(seconds//3600):02d}:{int((seconds%3600)//60):02d}:{int(seconds%60):02d}"
                    }]}
                except Exception as e:
                    print(f"Error parsing timestamp: {e}")
                    formatted_transcription = {"00:00:00 - 00:00:30": [{
                        'start': 0.0,
                        'text': str(transcription),
                        'display_time': '00:00:00'
                    }]}
            
            text_content = get_text_from_subtitles(transcription)
            summary = summarize_transcript(text_content)
            return formatted_transcription, False, summary
            
        except Exception as e:
            raise Exception(f"Whisper transcription failed: {str(e)}")
    except Exception as e:
        print(f"Debug - Error in get_transcription: {str(e)}")
        raise

class TranscriptionResponse(BaseModel):
    transcriptions: Dict[str, List[Dict[str, Any]]]
    summary: str
    source: str

class LinkedSummaryResponse(BaseModel):
    summary: str
    linked_segments: List[Dict]
    transcriptions: Dict[str, List[Dict[str, Any]]]
    source: str

def split_summary_into_sentences(summary: str) -> List[str]:
    """Split summary text into meaningful sentences."""
    # Simple sentence splitting on periods followed by space
    sentences = [s.strip() for s in summary.split('.') if s.strip()]
    return sentences

# Create a global instance of VideoVectorStore
vector_store_instance = VideoVectorStore()

@app.post("/transcribe", response_model=LinkedSummaryResponse)
async def transcribe_youtube_video(request: VideoRequest):
    try:
        print(f"Received URL: {request.youtube_video_url}")
        
        transcriptions, is_youtube, summary = await get_transcription(request.youtube_video_url)
        if not transcriptions:
            raise HTTPException(status_code=404, detail="Transcription failed")
        
        # Remove automatic vector search and just return the basic response
        return LinkedSummaryResponse(
            summary=summary,
            linked_segments=[],  # Empty list initially
            transcriptions=transcriptions,
            source="youtube" if is_youtube else "whisper"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
class MatchRequest(BaseModel):
    paragraph_text: str

class MatchResponse(BaseModel):
    timestamp: float
    display_time: str
    source_segment: str

@app.post("/match-segment", response_model=MatchResponse)
async def match_segment(request: MatchRequest):
    try:
        # Use very low threshold for matching with new normalization
        matches = vector_store_instance.find_matching_segments(request.paragraph_text, threshold=0.01)
        if matches and len(matches) > 0:
            best_match = matches[0]
            return MatchResponse(
                timestamp=best_match['timestamp'],
                display_time=best_match['display_time'],
                source_segment=best_match['source_segment']
            )
        raise HTTPException(status_code=404, detail="No matching segment found")
    except Exception as e:
        print(f"Match segment error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
    uvicorn.run(app, host="localhost", port=8000)
