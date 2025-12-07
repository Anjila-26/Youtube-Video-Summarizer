import os
import shutil
import yt_dlp
from moviepy.editor import AudioFileClip
import re
import requests

def setup_output_directory(output_dir):
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

def download_youtube_video_and_audio(video_url, output_dir='Saved_Media'):
    setup_output_directory(output_dir)

    # Commented as the video download is not required
    # video_options = {
    #     'format': 'best',
    #     'outtmpl': os.path.join(output_dir, 'video.%(ext)s'),
    # }

    audio_options = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, 'audio.%(ext)s'),
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['hls', 'dash']
            }
        },
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_warnings': False,
        'verbose': True,
    }

    # for download_options in [video_options, audio_options]:

    with yt_dlp.YoutubeDL(audio_options) as youtube_downloader:
        youtube_downloader.download([video_url])

    print("Video and audio download completed!")

def convert_audio_to_mp3(input_audio_path, output_mp3_path):
    audio = AudioFileClip(input_audio_path)
    audio.write_audiofile(output_mp3_path)
    audio.close()
    print("Audio conversion to MP3 completed!")

def process_youtube_video(video_url):
    output_dir = 'Saved_Media'
    
    download_youtube_video_and_audio(video_url, output_dir)
    
    input_audio_path = os.path.join(output_dir, 'audio.webm')
    output_mp3_path = os.path.join(output_dir, 'audio.mp3')
    
    convert_audio_to_mp3(input_audio_path, output_mp3_path)

def clean_captions(raw_captions):
    try:
        lines = raw_captions.decode('utf-8').split('\n')
        cleaned_lines = []
        timestamp_pattern = re.compile(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}')
        current_timestamp = None
        current_text = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if timestamp_pattern.match(line):
                if current_timestamp and current_text:
                    cleaned_lines.append(f"{current_timestamp}\n{' '.join(current_text)}")
                current_timestamp = line
                current_text = []
            elif not line.startswith('WEBVTT') and not line.startswith('Kind:') and not line.startswith('Language:'):
                current_text.append(line)
        
        # Don't forget the last group
        if current_timestamp and current_text:
            cleaned_lines.append(f"{current_timestamp}\n{' '.join(current_text)}")
        
        return '\n'.join(cleaned_lines)
    except Exception as e:
        print(f"Error in clean_captions: {e}")
        return ""

def extract_subtitles(video_url):
    subtitle_options = {
        'writesubtitles': True,
        'subtitleslangs': ['en'],
        'subtitlesformat': 'vtt',
        'skip_download': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['hls', 'dash']
            }
        },
        'nocheckcertificate': True,
    }

    with yt_dlp.YoutubeDL(subtitle_options) as youtube_downloader:
        try:
            info_dict = youtube_downloader.extract_info(video_url, download=False)
            
            # Debug prints
            print("Debug - Available subtitles:", info_dict.get('subtitles', {}))
            print("Debug - Available auto captions:", info_dict.get('automatic_captions', {}))
            
            # Try manual subtitles first
            if 'en' in info_dict.get('subtitles', {}):
                subtitles = info_dict['subtitles']['en']
            # Then try automatic captions
            elif 'en' in info_dict.get('automatic_captions', {}):
                subtitles = info_dict['automatic_captions']['en']
            else:
                print("No English subtitles found")
                return None
            
            # Try to get VTT format subtitle
            vtt_subtitle = None
            for fmt in subtitles:
                if fmt.get('ext') == 'vtt':
                    vtt_subtitle = fmt
                    break
            
            if vtt_subtitle:
                subtitle_url = vtt_subtitle.get('url')
                if subtitle_url:
                    print(f"Debug - Fetching subtitle URL: {subtitle_url}")
                    response = requests.get(subtitle_url)
                    if response.status_code == 200:
                        raw_subtitles = response.content
                        if b'WEBVTT' in raw_subtitles:
                            return parse_subtitles_to_dict(clean_captions(raw_subtitles))
                        else:
                            print("Debug - Invalid VTT content received")
                            return None
            
            print("No suitable VTT subtitles found")
            return None
            
        except Exception as e:
            print(f"Error extracting subtitles: {e}")
            return None

def parse_subtitles_to_dict(subtitles_text):
    if not subtitles_text:
        return {}
    
    lines = subtitles_text.split('\n')
    subtitle_dict = {}
    current_timestamp = None
    
    timestamp_pattern = re.compile(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}')
    
    for line in lines:
        if timestamp_pattern.match(line):
            current_timestamp = line
            subtitle_dict[current_timestamp] = ""
        elif current_timestamp and line.strip():
            subtitle_dict[current_timestamp] = subtitle_dict[current_timestamp] + " " + line.strip()
    
    return subtitle_dict

def timestamp_to_seconds(timestamp):
    # Extract the first timestamp from the range (before -->)
    start_time = timestamp.split('-->')[0].strip()
    # Parse HH:MM:SS.mmm format
    h, m, s = start_time.split(':')
    seconds = float(h) * 3600 + float(m) * 60 + float(s.replace(',', '.'))
    return int(seconds)

def group_subtitles_by_interval(subtitle_dict, interval=30):
    if not subtitle_dict:
        return {}

    grouped_subtitles = {}
    
    for timestamp, text in sorted(subtitle_dict.items(), key=lambda x: timestamp_to_seconds(x[0])):
        seconds = timestamp_to_seconds(timestamp)
        start_seconds = (seconds // interval) * interval
        end_seconds = start_seconds + interval

        # Convert seconds to HH:MM:SS format
        start_time = f"{start_seconds // 3600:02}:{(start_seconds % 3600) // 60:02}:{start_seconds % 60:02}"
        end_time = f"{end_seconds // 3600:02}:{(end_seconds % 3600) // 60:02}:{end_seconds % 60:02}"

        time_range = f"{start_time} - {end_time}"
        
        if time_range not in grouped_subtitles:
            grouped_subtitles[time_range] = []
        
        grouped_subtitles[time_range].append(text)

    # Join texts in each group
    return {k: ' '.join(v) for k, v in grouped_subtitles.items()}

# Modify the main block to demonstrate the new format
if __name__ == "__main__":
    youtube_video_url = "https://www.youtube.com/watch?v=eIho2S0ZahI"
    process_youtube_video(youtube_video_url)

    # Get and process subtitles
    subtitles_text = extract_subtitles(youtube_video_url)
    if subtitles_text:
        subtitle_dict = parse_subtitles_to_dict(subtitles_text)
        grouped_subtitles = group_subtitles_by_interval(subtitle_dict)
        
        for timestamp, text in grouped_subtitles.items():
            print(f'Timestamp: {timestamp}')
            print(f'Subtitle: {text}\n')
