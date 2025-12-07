from langchain.embeddings import OllamaEmbeddings
from langchain.vectorstores.chroma import Chroma
from typing import Dict, List, Union
import chromadb
import os

class VideoVectorStore:
    _instance = None
    _store = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VideoVectorStore, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if not self.initialized:
            self.embeddings = OllamaEmbeddings(model="quantphi")
            self.persist_directory = "chroma_db"
            if not os.path.exists(self.persist_directory):
                os.makedirs(self.persist_directory)
            self.initialized = True
            self._load_existing_store()

    def _load_existing_store(self):
        try:
            if VideoVectorStore._store is None:
                VideoVectorStore._store = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embeddings
                )
            self.vector_store = VideoVectorStore._store
        except Exception as e:
            print(f"No existing store found or error loading: {e}")
            self.vector_store = None

    def create_segment_embeddings(self, segments: Dict[str, List[Dict]]):
        # Creates vector embeddings of text segments with timestamps
        texts = []
        metadatas = []
        for time_range, segment_list in segments.items():
            for segment in segment_list:
                texts.append(segment['text'])
                metadatas.append({
                    'timestamp': str(segment['start']),
                    'display_time': segment['display_time']
                })
        
        # Create or update collection
        VideoVectorStore._store = Chroma.from_texts(
            texts=texts,
            embedding=self.embeddings,
            metadatas=metadatas,
            persist_directory=self.persist_directory
        )
        self.vector_store = VideoVectorStore._store
        return self.vector_store

    def find_matching_segments(self, summary: str, threshold: float = 0.2) -> List[Dict[str, Union[str, float]]]:
        """
        Finds segments matching the summary text using similarity scores.

        Args:
            summary (str): The summary text to search for matching segments.
            threshold (float): The minimum normalized similarity score for a segment to be considered a match.

        Returns:
            List[Dict[str, Union[str, float]]]: A list of matching segments with metadata and similarity scores.
        """
        if not self.vector_store:
            raise ValueError("No vector store available. Initialize or load a store first.")
        
        try:
            results = self.vector_store.similarity_search_with_relevance_scores(summary, k=5)
            if not results:
                return []
            
            scores = [score for _, score in results]
            min_score, max_score = min(scores), max(scores)
            score_range = max(max_score - min_score, 1)  # Avoid division by zero
            
            linked_segments = [
                {
                    'summary_text': summary,
                    'source_segment': doc.page_content,
                    'timestamp': float(doc.metadata['timestamp']),
                    'display_time': doc.metadata['display_time'],
                    'similarity_score': 1 - ((abs(score) - abs(min_score)) / score_range),
                }
                for doc, score in results
                if 1 - ((abs(score) - abs(min_score)) / score_range) >= threshold
            ]
            
            return sorted(linked_segments, key=lambda x: x['similarity_score'], reverse=True)
        
        except Exception as e:
            raise RuntimeError(f"Error during similarity search: {e}")

            
        except Exception as e:
            print(f"Error in similarity search: {e}")
            return []
