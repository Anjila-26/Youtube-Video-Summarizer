'use client';

import React, { useState, useEffect, useRef } from 'react';
import YouTube from 'react-youtube';
import { Send, FileText, FileSpreadsheet, Link } from 'lucide-react'; // Add Link to imports
import axios from 'axios';
import { Roboto_Flex } from 'next/font/google';
import ReactMarkdown from "react-markdown";
import { link } from 'fs';

const robotoFlex = Roboto_Flex({
    subsets: ['latin'],
    display: 'swap',
});

interface VideoRequestBody {
    youtube_video_url: string;
}

interface YouTubePlayer {
    seekTo(seconds: number, allowSeekAhead: boolean): void;
    playVideo(): void;
    getCurrentTime(): Promise<number>;
    getPlayerState(): number;
}

interface PlayerRef {
    internalPlayer: YouTubePlayer;
}       

interface TranscriptSegment {
    start: number;
    text: string;
    display_time: string;
}

interface LinkedSegment {
    summary_text: string;
    source_segment: string;
    timestamp: number;
    display_time: string;
}

interface LinkedSummaryResponse {
    transcriptions: {
        [timeRange: string]: TranscriptSegment[];
    };
    summary: string;
    linked_segments: LinkedSegment[];
    source: 'youtube' | 'whisper';
}

interface TranscriptionState {
    data: {
        transcriptions: {
            [timeRange: string]: TranscriptSegment[];
        };
        summary: string;
        linked_segments: LinkedSegment[];
    };
    source: 'youtube' | 'whisper' | null;
    loading: boolean;
}

interface MatchRequest {
    paragraph_text: string;
}   

interface MatchResponse {
    timestamp: number;
    display_time: string;
    source_segment: string;
}

export default function Hero() {
    const [videoUrl, setVideoUrl] = useState('');
    const [videoId, setVideoId] = useState('');
    const [transcription, setTranscription] = useState<TranscriptionState>({
        data: {
            transcriptions: {},
            summary: '',
            linked_segments: []  // Initialize as empty array
        },
        source: null,
        loading: false
    });
    const [error, setError] = useState<string | null>(null);
    const [videoError, setVideoError] = useState(false);
    const [playerRef, setPlayerRef] = useState<PlayerRef | null>(null);
    const [isPlayerReady, setIsPlayerReady] = useState(false);
    const playerReadyRef = useRef(false);
    const initializationTimer = useRef<NodeJS.Timeout | null>(null);
    const [currentTime, setCurrentTime] = useState(0);
    const [timeTracker, setTimeTracker] = useState<NodeJS.Timer | null>(null);  
    const [activeView, setActiveView] = useState<'transcript' | 'summary'>('transcript');
    const [paragraphMatches, setParagraphMatches] = useState<Map<string, LinkedSegment>>(new Map());
    const [loadingLinks, setLoadingLinks] = useState<{ [key: number]: boolean }>({});

    // Add function to get matches from backend
    const getMatchingSegment = async (paragraphText: string): Promise<MatchResponse | null> => {
        try {
            const response = await fetch('http://localhost:8000/match-segment', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ paragraph_text: paragraphText })
            });
    
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Error matching segment:', error);
            return null;
        }
    };

    const extractVideoId = (url: string) => {
        const regex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/;
        const match = url.match(regex);
        return match ? match[1] : '';
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setTranscription(prev => ({ ...prev, loading: true }));
        setError(null);
        setVideoError(false);
        const extractedVideoId = extractVideoId(videoUrl);

        if (!extractedVideoId) {
            setError('Invalid YouTube URL');
            setTranscription(prev => ({ ...prev, loading: false }));
            return;
        }

        try {
            setVideoId(extractedVideoId);
            const requestBody: VideoRequestBody = {
                youtube_video_url: videoUrl
            };
            
            const response = await axios.post<LinkedSummaryResponse>(
                'http://localhost:8000/transcribe',
                requestBody,
                {
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }
            );

            if (response.data) {
                setTranscription({
                    data: {
                        transcriptions: response.data.transcriptions,
                        summary: response.data.summary,
                        linked_segments: response.data.linked_segments
                    },
                    source: response.data.source,
                    loading: false
                });
            } else {
                throw new Error('No transcription found');
            }
        } catch (err) {
            if (axios.isAxiosError(err)) {
                const errorMessage = err.response?.data?.detail || err.message;
                setError(errorMessage);
                console.error('API Error:', errorMessage);
            } else {
                setError('An unexpected error occurred');
                console.error('Unexpected Error:', err);
            }
            setTranscription({ data: { transcriptions: {}, summary: '', linked_segments: [] }, source: null, loading: false });
        }
    };

    const handleVideoError = () => {
        setVideoError(true);
        setError('Failed to load video');
    };

    const seekToTime = async (seconds: number): Promise<void> => {
        const maxAttempts = 10;
        let attempts = 0;
    
        const attemptSeek = async (): Promise<boolean> => {
            if (!playerRef?.internalPlayer) {
                return false;
            }
    
            try {
                const playerState = playerRef.internalPlayer.getPlayerState();
                // Check if player is in a valid state (-1: unstarted, 0: ended, 1: playing, 2: paused, 3: buffering, 5: cued)
                if (playerState !== undefined) {
                    await playerRef.internalPlayer.seekTo(seconds, true);
                    await playerRef.internalPlayer.playVideo();
                    return true;
                }
            } catch (error) {
                console.warn('Seek attempt failed:', error);
            }
            return false;
        };
    
        while (attempts < maxAttempts) {
            if (await attemptSeek()) {
                return;
            }
            attempts++;
            if (attempts < maxAttempts) {
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }
        
        console.error('Failed to seek after maximum attempts');
    };     

    const onPlayerReady = (event: { target: PlayerRef['internalPlayer'] }) => {
        setPlayerRef({ internalPlayer: event.target });
        setIsPlayerReady(true);
        playerReadyRef.current = true;
    
        // Clear any existing timer
        if (timeTracker) {
            clearInterval(timeTracker as NodeJS.Timeout);
        }
    
        // Set up time tracking
        const interval = setInterval(async () => {
            try {
                if (event.target?.getCurrentTime) {
                    const time = await event.target.getCurrentTime();
                    setCurrentTime(time);
                }
            } catch (error) {
                console.warn('Error getting current time:', error);
            }
        }, 1000);
    
        setTimeTracker(interval);
    };    

    const onPlayerStateChange = (event: { data: number }) => {
        // Update player ready state based on player state
        const isReady = event.data !== -1; // -1 means unstarted
        setIsPlayerReady(isReady);
        playerReadyRef.current = isReady;
    };


    const logCurrentTime = () => {
        if (playerRef?.internalPlayer) {
            console.log('Current Time:', playerRef.internalPlayer.getCurrentTime());
        }
    };
    
    // Cleanup interval on component unmount
        // Add this cleanup effect
    useEffect(() => {
        return () => {
            if (initializationTimer.current) {
                clearTimeout(initializationTimer.current);
            }
            if (timeTracker) {
                clearInterval(timeTracker as NodeJS.Timeout);
            }
        };
    }, []);

    const handleLinkClick = async (paragraph: string, index: number) => {
        try {
            setLoadingLinks(prev => ({ ...prev, [index]: true }));
            const match = await getMatchingSegment(paragraph.trim());
            if (match) {
                await seekToTime(match.timestamp);
            }
        } catch (error) {
            console.error('Error matching segment:', error);
        } finally {
            setLoadingLinks(prev => ({ ...prev, [index]: false }));
        }
    };

    return (
        <div className={`min-h-screen bg-gradient-to-br from-[#E3EAFF] via-[#EFF2FF] to-[#E3EAFF] flex items-center justify-center p-4 ${robotoFlex.className}`}>
            <div className="bg-white bg-opacity-30 backdrop-filter backdrop-blur-lg rounded-3xl p-8 w-full max-w-7xl shadow-2xl">
                <div className="flex flex-col items-center mb-8">
                    <h1 className="text-6xl font-semibold text-black mb-6">YOUTUBE SUMMARIZER</h1>
                </div>
                <form onSubmit={handleSubmit} className="mb-10">
                    <div className="relative max-w-4xl mx-auto">
                        <input
                            type="text"
                            value={videoUrl}
                            onChange={(e) => setVideoUrl(e.target.value)}
                            placeholder="Paste your YouTube URL here..."
                            className="w-full px-8 py-5 bg-white bg-opacity-50 rounded-full text-lg text-black placeholder-black/60 focus:outline-none focus:ring-2 focus:ring-[#5661F6] focus:bg-opacity-70 transition-all duration-300 font-semibold"
                        />
                        <button
                            type="submit"
                            disabled={transcription.loading}
                            className="absolute right-3 top-2.5 px-8 py-3 bg-[#5661F6] hover:bg-[#5661F6]/80 text-white font-semibold rounded-full transition-colors duration-300 focus:outline-none focus:ring-2 focus:ring-[#5661F6] focus:ring-offset-2 focus:ring-offset-[#E3EAFF] disabled:bg-[#5661F6]/50 disabled:cursor-not-allowed"
                        >
                            {transcription.loading ? 'Loading...' : <Send size={28} />}
                        </button>
                    </div>
                    {error && <p className="text-black/70 mt-4 text-center text-lg font-semibold">{error}</p>}
                </form>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {videoId && !videoError && (
                        <div className="lg:col-span-1">
                            <YouTube
                                videoId={videoId}
                                className="w-full rounded-xl overflow-hidden"
                                opts={{
                                    height: '450',
                                    width: '100%',
                                    playerVars: {
                                        autoplay: 0,
                                        enablejsapi: 1,
                                    },
                                }}
                                onReady={onPlayerReady}
                                onStateChange={onPlayerStateChange}
                                onError={handleVideoError}
                            />
                        </div>
                    )}

                    {Object.keys(transcription.data.transcriptions).length > 0 && (
                        <div className="lg:col-span-1 bg-white bg-opacity-40 rounded-2xl p-8 backdrop-filter backdrop-blur-sm max-h-[700px] overflow-hidden">
                            <div className="flex flex-col space-y-4">
                                <div className="flex space-x-4 mb-2">
                                    <button
                                        onClick={() => setActiveView('transcript')}
                                        className={`flex items-center space-x-2 px-4 py-2 rounded-full transition-all duration-300 ${
                                            activeView === 'transcript'
                                                ? 'bg-[#5661F6] text-white'
                                                : 'bg-white/50 text-black hover:bg-[#5661F6]/10'
                                        }`}
                                    >
                                        <FileText size={18} />
                                        <span className="font-semibold">Transcript</span>
                                    </button>
                                    <button
                                        onClick={() => setActiveView('summary')}
                                        className={`flex items-center space-x-2 px-4 py-2 rounded-full transition-all duration-300 ${
                                            activeView === 'summary'
                                                ? 'bg-[#5661F6] text-white'
                                                : 'bg-white/50 text-black hover:bg-[#5661F6]/10'
                                        }`}
                                    >
                                        <FileSpreadsheet size={18} />
                                        <span className="font-semibold">Summary</span>
                                    </button>
                                </div>

                                <div className="flex justify-between items-center">
                                    <h2 className="text-3xl font-semibold text-black">
                                        {activeView === 'transcript' ? 'Interactive Transcript' : 'Video Summary'}
                                    </h2>
                                    <span className="px-4 py-2 bg-[#5661F6] rounded-full text-base text-white font-semibold">
                                        Source: {transcription.source === 'youtube' ? 'YouTube' : 'Whisper AI'}
                                    </span>
                                </div>

                                <div className="overflow-y-auto custom-scrollbar max-h-[580px]">
                                    {activeView === 'transcript' ? (
                                        <div className="space-y-6">
                                            {Object.entries(transcription.data.transcriptions).map(([timeRange, segments]) => (
                                                <div key={timeRange} className="border-b border-black/10 pb-4">
                                                    <div className="space-y-2">
                                                    {segments.map((segment, idx) => (
                                                        <div
                                                            key={idx}
                                                            onClick={async () => {
                                                                console.log(`Seeking to ${segment.start} seconds`);
                                                                await seekToTime(segment.start);
                                                            }}
                                                            className="cursor-pointer p-2 rounded transition-colors duration-300 hover:bg-black/5"
                                                        >
                                                            <span className="text-xs text-black/60 font-mono font-semibold">
                                                                {segment.display_time}
                                                            </span>
                                                            <p className="text-black hover:text-black/80 font-semibold">
                                                                {segment.text}
                                                            </p>
                                                        </div>
                                                    ))}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="bg-white/30 rounded-xl p-6">
                                            {transcription.data.summary ? (
                                                <div className="space-y-6">
                                                    <div className="bg-white/50 rounded-lg p-6">
                                                        <div className="text-black space-y-4">
                                                            {/* Replace split('\n') with a more specific split for numbered points */}
                                                            {transcription.data.summary.split(/(?=\d+\.\s)/).map((paragraph, index) => (
                                                                <div key={index} className="flex items-start space-x-2 p-4 rounded-lg hover:bg-white/30 transition-colors">
                                                                    <p className="flex-grow text-lg">{paragraph.trim()}</p>
                                                                    {paragraph.trim() && (
                                                                        // Update button click handler
                                                                        <button
                                                                            onClick={() => handleLinkClick(paragraph.trim(), index)}
                                                                            disabled={loadingLinks[index]}
                                                                            className="mt-1 p-2 hover:bg-[#5661F6]/10 rounded-full transition-colors group"
                                                                            title="Jump to relevant timestamp"
                                                                        >
                                                                            {loadingLinks[index] ? (
                                                                                <div className="w-5 h-5 border-2 border-[#5661F6] border-t-transparent rounded-full animate-spin" />
                                                                            ) : (
                                                                                <Link size={20} className="text-[#5661F6] group-hover:scale-110 transition-transform" />
                                                                            )}
                                                                        </button>
                                                                    )}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                </div>
                                            ) : (
                                                <p className="text-black/70 text-lg font-semibold">
                                                    No summary available for this video.
                                                </p>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// Add these styles to your globals.css or create a new style block
const styles = `
    /* Custom Scrollbar Styles */
    .scrollbar-thin::-webkit-scrollbar {
        width: 4px;
    }

    .scrollbar-thin::-webkit-scrollbar-track {
        background: transparent;
    }

    .scrollbar-thin::-webkit-scrollbar-thumb {
        background: rgba(86, 97, 246, 0.4);
        border-radius: 20px;
    }

    .scrollbar-thin::-webkit-scrollbar-thumb:hover {
        background: rgba(86, 97, 246, 0.6);
    }
`;
