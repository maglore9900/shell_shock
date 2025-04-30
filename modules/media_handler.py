# modules/media_handler.py
import os
import pygame
import tempfile
import json
import time
import random
import ffmpeg
import urllib.request
from pathlib import Path
from datetime import datetime
from pydub import AudioSegment
from modules.logging_utils import app_logger as log
from typing import Dict, Any, Optional, List, Union, TypedDict, Literal, TypeVar, Generic

class MediaHandler:
    """Handles media operations like loading, converting, indexing, and getting track information."""
    
    def __init__(self):
        """Initialize the media handler."""
        # Create temp directory for conversions
        self.temp_dir = tempfile.mkdtemp()
        self.converted_files = {}
        
        # Define supported formats
        self.pygame_supported = ['.mp3', '.wav', '.ogg']
        self.pydub_supported = ['.m4a', '.aac', '.flac', '.mp4', '.wma']
        self.all_supported = self.pygame_supported + self.pydub_supported
        
        # Media indexing properties
        self.media_index = {}  # Path -> metadata
        self.media_locations = []  # List of directories being indexed
        self.last_update = None  # When index was last updated
        self.index_file = "media_index.json"  # Where to store the index
        
        # Initialize pygame mixer if not already initialized
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100)
        
        # Load any existing index
        self._load_index()
    
    def get_supported_formats(self):
        """Get a list of all supported file formats."""
        return self.all_supported
    
    def add_media_location(self, directories: List[str]):
        """Add a new location or locations to be indexed.
        
        Args:
            directories (List[str]): Path to the directory to index
        """
        for directory in directories:
            directory = os.path.abspath(directory)
            if directory not in self.media_locations and os.path.exists(directory):
                self.media_locations.append(directory)
    
    def remove_media_location(self, directory):
        """Remove a location from the index.
        
        Args:
            directory (str): Path to the directory to remove
            
        Returns:
            bool: True if removed, False if not found
        """
        directory = os.path.abspath(directory)
        if directory in self.media_locations:
            self.media_locations.remove(directory)
            return True
        return False
    
    def get_media_locations(self):
        """Get all media locations being indexed.
        
        Returns:
            list: List of directory paths
        """
        return self.media_locations.copy()
    
    def update_media_index(self, force=False):
        """Update the media index by scanning provided file paths.
        
        Args:
            file_paths (list): List of file path strings to process
            force (bool): Force complete rebuild even if not needed
            
        Returns:
            int: Number of files indexed
        """
        # Check if we need to update
        if not force and self.last_update and time.time() - self.last_update < 3600:
            # Skip if updated less than an hour ago and not forced
            return len(self.media_index)
        
        # Track invalid entries to remove
        to_remove = set(self.media_index.keys())
        
        # Process each file path in the list
        for file_path in self.media_index:
            # print(f"Indexing: {file_path}")
            # Create or update file entry
            filename = os.path.basename(file_path)
            
            # Get the directory from the file path
            directory = os.path.dirname(file_path)
            
            # If file already in index, mark as still valid
            if file_path in to_remove:
                to_remove.remove(file_path)
            
            # Get file metadata if not already indexed
            if file_path not in self.media_index:
                # Create basic metadata
                duration = self.get_track_duration(file_path)
                
                self.media_index[file_path] = {
                    'filename': filename,
                    'path': file_path,
                    'directory': directory,
                    'duration': duration,
                    'last_played': None,
                    'play_count': 0,
                    'added_on': datetime.now().isoformat()
                }
        
        # Remove files that no longer exist
        for file_path in to_remove:
            if file_path in self.media_index:
                del self.media_index[file_path]
        
        self.last_update = time.time()
        self._save_index()
        
        return len(self.media_index)
    
    def get_all_indexed_tracks(self, sort_method='name', shuffle=False):
        """Get all tracks from the index, with optional sorting.
        
        Args:
            sort_method (str): How to sort - 'name', 'date', 'random'
            shuffle (bool): Whether to shuffle the results
            
        Returns:
            list: Paths to all tracks
        """
        # Get all tracks
        tracks = list(self.media_index.keys())
        
        # Apply sorting
        if shuffle or sort_method == 'random':
            random.shuffle(tracks)
        elif sort_method == 'name':
            tracks.sort(key=lambda x: os.path.basename(x).lower())
        elif sort_method == 'date':
            # Sort by added_on date if available, otherwise modification time
            tracks.sort(key=lambda x: self.media_index[x].get('added_on', 
                                                             datetime.fromtimestamp(os.path.getmtime(x)).isoformat()))
        
        return tracks
    
    def search_tracks(self, query, limit=20):
        """Search for media files by name across all indexed locations.
        
        Args:
            query (str): Search string
            limit (int): Maximum number of results
            
        Returns:
            list: Media files matching the query
        """
        if not query:
            return []
            
        query = query.lower()
        results = []
        
        # Score each file
        for file_path, metadata in self.media_index.items():
            filename = metadata['filename'].lower()
            
            # Simple substring search - for fuzzy search, install fuzzywuzzy
            if query in filename:
                # Calculate a simple score based on match position and length
                position = filename.find(query)
                score = 100 - (position * 5)  # Higher score for matches at beginning
                results.append((score, file_path, metadata))
                continue
            
            # Try to match individual words
            query_parts = query.split()
            match_count = 0
            
            for part in query_parts:
                if part in filename:
                    match_count += 1
            
            # If all parts match, add with score
            if match_count == len(query_parts) and match_count > 0:
                score = 70 + (match_count * 5)  # Bonus for matching multiple parts
                results.append((score, file_path, metadata))
            # Partial matches if they're good enough
            elif match_count > 0 and match_count >= len(query_parts) / 2:
                score = 50 + (match_count * 10)  # Lower score for partial matches
                results.append((score, file_path, metadata))
        
        # Sort by score (highest first)
        results.sort(reverse=True, key=lambda x: x[0])
        
        # Return file paths for top results, limited to requested amount
        return [item[1] for item in results[:limit]]
    
    def get_track_metadata(self, file_path):
        """Get metadata for a track from the index.
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            dict: File metadata or None if not found
        """
        return self.media_index.get(file_path)
    
    def update_play_stats(self, file_path):
        """Update play statistics for a file in the index.
        
        Args:
            file_path (str): Path to the file
        """
        if file_path in self.media_index:
            self.media_index[file_path]['last_played'] = datetime.now().isoformat()
            self.media_index[file_path]['play_count'] += 1
            self._save_index()
    
    def load_media_from_directory(self, directory, recursive=False):
        """Load all supported media files from a directory.
        
        Args:
            directory (str): Directory path to scan
            recursive (bool): Whether to scan subdirectories
            
        Returns:
            list: Paths to all media files found
        """
        media_files = []
        
        if not os.path.exists(directory):
            return media_files
            
        # Use pathlib for better path handling
        root_dir = Path(directory)
        
        # Get the iterator (recursive or non-recursive)
        if recursive:
            file_iterator = root_dir.glob('**/*')  # Recursive
        else:
            file_iterator = root_dir.glob('*')  # Non-recursive
        
        # Process each file
        for file_path in file_iterator:
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in self.all_supported:
                    media_files.append(str(file_path))
        
        return media_files
    
    def convert_if_needed(self, file_path):
        """Convert non-pygame supported files to .wav format.
        
        Args:
            file_path (str): Path to the audio file
            
        Returns:
            str: Path to a playable file (original or converted)
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        # If file is already playable by pygame, return original
        if ext in self.pygame_supported:
            return file_path
            
        # Check if we've already converted this file
        if file_path in self.converted_files:
            return self.converted_files[file_path]
        
        try:
            # Load the audio file using pydub
            if ext in ['.m4a', '.aac', '.mp4']:
                sound = AudioSegment.from_file(file_path, format="m4a")
            elif ext == '.flac':
                sound = AudioSegment.from_file(file_path, format="flac")
            elif ext == '.wma':
                sound = AudioSegment.from_file(file_path, format="wma")
            else:
                sound = AudioSegment.from_file(file_path)
            
            # Create a temporary WAV file
            temp_file = os.path.join(self.temp_dir, os.path.basename(file_path) + '.wav')
            sound.export(temp_file, format="wav")
            
            self.converted_files[file_path] = temp_file
            return temp_file
        except Exception as e:
            print(f"Error converting file: {e}")
            return None

    def convert_to_mp3(self, input_file, output_file):
        """Convert an audio file to MP3 format using ffmpeg"""
        try:
            # Use ffmpeg to convert the file
            (
                ffmpeg
                .input(input_file)
                .output(output_file, acodec='libmp3lame', ab='192k')
                .run(quiet=True, overwrite_output=True)
            )
            return True
        except Exception as e:
            print(f"Error converting audio: {e}")
            return False
    
    def get_track_duration(self, file_path):
        """Get the duration of an audio track in seconds.
        
        Args:
            file_path (str): Path to the audio file
            
        Returns:
            float: Duration in seconds
        """
        try:
            # Try using pydub first (more reliable)
            try:
                audio = AudioSegment.from_file(file_path)
                return len(audio) / 1000  # Convert from ms to seconds
            except Exception as e:
                print(f"Pydub error: {e}")
                
                # Fallback to pygame for supported formats
                ext = os.path.splitext(file_path)[1].lower()
                if ext in self.pygame_supported:
                    try:
                        sound = pygame.mixer.Sound(file_path)
                        return sound.get_length()
                    except Exception as e:
                        print(f"Pygame error: {e}")
                
                # Default duration
                return 180  # 3 minutes
        except Exception as e:
            print(f"Duration detection error: {e}")
            return 180  # Default 3 minutes
    
    def _load_index(self):
        """Load the index from disk or create it if it doesn't exist."""
        try:
            if os.path.exists(self.index_file):
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
                    self.media_index = data.get('index', {})
                    self.media_locations = data.get('locations', [])
                    self.last_update = data.get('last_update')
            else:
                # Initialize empty data structures
                self.media_index = {}
                self.last_update = None
                # Create the file with empty data
                self._save_index()
                print(f"Created new index file: {self.index_file}")
        except Exception as e:
            print(f"Error loading/creating index: {e}")
            # Initialize empty if loading fails
            self.media_index = {}
            self.last_update = None
    
    def _save_index(self):
        """Save the index to disk."""
        try:
            data = {
                'index': self.media_index,
                'locations': self.media_locations,
                'last_update': self.last_update
            }
            with open(self.index_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving index: {e}")
    
    def cleanup(self):
        """Clean up temporary files."""
        # Save index before cleanup
        self._save_index()
        
        # Clean up converted files
        for temp_file in self.converted_files.values():
            try:
                os.remove(temp_file)
            except:
                pass
        try:
            os.rmdir(self.temp_dir)
        except:
            pass
    
    # NEW AUDIO PLAYBACK METHODS
    
    def play_audio(self, file_path, start_pos=0.0, loops=0):
        """
        Load and play an audio file.
        
        Args:
            file_path (str): Path to the audio file
            start_pos (float): Start position in seconds
            loops (int): Number of times to repeat (-1 for infinite)
            
        Returns:
            tuple: (success, temp_file_path or None)
        """
        try:
            # Convert file if needed
            playable_file = self.convert_if_needed(file_path)
            if not playable_file:
                print(f"Cannot play {os.path.basename(file_path)}: format not supported")
                return False, None
            
            # Load and play the file
            pygame.mixer.music.load(playable_file)
            pygame.mixer.music.play(loops, start_pos)
            
            # Return success and temp file path if one was created
            temp_file = playable_file if playable_file != file_path else None
            return True, temp_file
        except Exception as e:
            print(f"Error playing audio: {e}")
            return False, None

    def pause_audio(self):
        """
        Pause audio playback.
        
        Returns:
            bool: True if successful
        """
        try:
            pygame.mixer.music.pause()
            return True
        except Exception as e:
            print(f"Error pausing audio: {e}")
            return False

    def resume_audio(self):
        """
        Resume paused audio playback.
        
        Returns:
            bool: True if successful
        """
        try:
            pygame.mixer.music.unpause()
            return True
        except Exception as e:
            print(f"Error resuming audio: {e}")
            return False

    def stop_audio(self):
        """
        Stop audio playback.
        
        Returns:
            bool: True if successful
        """
        try:
            pygame.mixer.music.stop()
            return True
        except Exception as e:
            print(f"Error stopping audio: {e}")
            return False

    def set_audio_volume(self, volume):
        """
        Set audio volume (0.0 to 1.0).
        
        Args:
            volume (float): Volume level between 0.0 and 1.0
            
        Returns:
            bool: True if successful
        """
        try:
            volume = max(0.0, min(1.0, volume))
            pygame.mixer.music.set_volume(volume)
            return True
        except Exception as e:
            print(f"Error setting volume: {e}")
            return False

    def is_audio_playing(self):
        """
        Check if audio is currently playing.
        
        Returns:
            bool: True if audio is playing
        """
        try:
            return pygame.mixer.music.get_busy()
        except Exception as e:
            print(f"Error checking playback status: {e}")
            return False

    def get_audio_position(self):
        """
        Get current playback position in milliseconds.
        
        Returns:
            int: Position in milliseconds or -1 if error
        """
        try:
            return pygame.mixer.music.get_pos()
        except Exception as e:
            print(f"Error getting position: {e}")
            return -1
            
    def cleanup_audio_file(self, file_path):
        """
        Safely remove a temporary audio file.
        
        Args:
            file_path (str): Path to the file to remove
            
        Returns:
            bool: True if successful or file didn't exist
        """
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                # If this was a converted file, remove it from our tracking dict
                for src, temp in list(self.converted_files.items()):
                    if temp == file_path:
                        del self.converted_files[src]
                return True
            except Exception as e:
                print(f"Error removing temp file: {e}")
                return False
        return True  # No file to clean up
    
    def download_media_file(self, url, file_name, download_dir=None):
        if not download_dir:
            download_dir=self.temp_dir 
        try:
            file_path = os.path.join(download_dir, file_name)
            if not os.path.exists(file_path):
                urllib.request.urlretrieve(url, file_path)
            return file_path
        except Exception as e:
            print(f"Error downloading {file_name}: {e}")