# modules/playlist_handler.py
import os
import time
import random

class PlaylistHandler:
    """Handles playlist operations like loading, saving, and managing playlists."""
    
    def __init__(self, playlists_dir="playlists"):
        """Initialize the playlist handler.
        
        Args:
            playlists_dir (str): Directory path for storing playlist files
        """
        self.playlists_dir = playlists_dir
        self.playlists = {}  # name -> {tracks, file}
        self.current_playlist = None
        
        # Create playlists directory if it doesn't exist
        if not os.path.exists(playlists_dir):
            try:
                os.makedirs(playlists_dir)
                print(f"Created playlists directory: {playlists_dir}")
            except Exception as e:
                print(f"Error creating playlists directory: {e}")
    
    def scan_playlists(self):
        """Scan for and load playlists from the playlists directory.
        
        Returns:
            dict: Loaded playlists mapping
        """

        # Clear existing playlists
        self.playlists = {
            "Local Media": {
            'tracks': [],  # Empty list to start with
            'file': None
            }
        }
        
        # Scan for .txt files in the playlists directory
        playlist_files = [f for f in os.listdir(self.playlists_dir) if f.endswith('.txt')]
        
        if not playlist_files:
            return self.playlists
        
        # Load each playlist file
        for playlist_file in playlist_files:
            default_name = os.path.splitext(playlist_file)[0]  # Default name is filename without extension
            playlist_path = os.path.join(self.playlists_dir, playlist_file)
            
            try:
                with open(playlist_path, 'r', encoding='utf-8') as f:
                    # Read and process lines
                    tracks = []
                    playlist_name = default_name  # Default to filename
                    
                    for line in f:
                        line = line.strip()
                        if line.startswith('#'):  # Skip comment lines
                            continue
                        elif line.lower().startswith('name:'):  # Extract playlist name
                            # Get everything after "name:" and strip whitespace
                            name_part = line[5:].strip()
                            if name_part:  # Only update if there's a name
                                playlist_name = name_part
                        elif line:  # Non-empty lines are track paths
                            # Check if the track exists
                            if os.path.exists(line):
                                tracks.append(line)
                            else:
                                print(f"Warning: Track not found: {line}")
                    
                    # Store the playlist if it has tracks
                    if tracks:
                        self.playlists[playlist_name] = {
                            'tracks': tracks,
                            'file': playlist_file  # Store the filename for saving
                        }
                        print(f"Loaded playlist: {playlist_name} ({len(tracks)} tracks)")
                    else:
                        print(f"Skipped empty playlist: {playlist_name}")
                        
            except Exception as e:
                print(f"Error loading playlist {default_name}: {e}")
        
        # Print loading summary
        print(f"\nLoaded {len(self.playlists)} playlists from {self.playlists_dir}")
        return self.playlists
    
    def save_playlist(self, playlist_name, tracks, file_name=None):
        """Save a playlist to a file.
        
        Args:
            playlist_name (str): Name of the playlist
            tracks (list): List of track paths to save
            file_name (str, optional): Filename to use. Defaults to None.
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        # Create the playlists directory if it doesn't exist
        if not os.path.exists(self.playlists_dir):
            try:
                os.makedirs(self.playlists_dir)
            except Exception as e:
                print(f"Error creating playlists directory: {e}")
                return False
        
        # If this playlist already exists, use its existing filename
        if playlist_name in self.playlists and not file_name:
            file_name = self.playlists[playlist_name]['file']
        
        # Otherwise, create a safe filename from the playlist name
        if not file_name:
            # Convert spaces to underscores and remove special characters
            safe_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in playlist_name)
            file_name = f"{safe_name}.txt"
        
        # Construct the file path
        playlist_path = os.path.join(self.playlists_dir, file_name)
        
        try:
            # Write the tracks to the file
            with open(playlist_path, 'w', encoding='utf-8') as f:
                f.write(f"# Playlist file created {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("# Format: 'name:' line specifies playlist name\n")
                f.write("# Everything else is either a comment (starts with #) or a track path\n\n")
                f.write(f"name: {playlist_name}\n\n")
                for track in tracks:
                    f.write(f"{track}\n")
            
            # Update the in-memory playlist
            self.playlists[playlist_name] = {
                'tracks': tracks,
                'file': file_name
            }
            
            print(f"Saved playlist: {playlist_name} ({len(tracks)} tracks)")
            return True
        except Exception as e:
            print(f"Error saving playlist {playlist_name}: {e}")
            return False
    
    def get_playlist(self, playlist_name):
        """Get a specific playlist's tracks.
        
        Args:
            playlist_name (str): Name of the playlist
            
        Returns:
            list: Tracks in the playlist, or empty list if not found
        """
        if playlist_name in self.playlists:
            return self.playlists[playlist_name]['tracks']
        return []
    
    def get_playlist_names(self):
        """Get all playlist names.
        
        Returns:
            list: List of playlist names
        """
        return list(self.playlists.keys())
    
    def create_playlist(self, playlist_name, tracks=None):
        """Create a new playlist.
        
        Args:
            playlist_name (str): Name of the new playlist
            tracks (list, optional): Initial tracks. Defaults to empty list.
            
        Returns:
            bool: True if created successfully, False otherwise
        """
        if tracks is None:
            tracks = []
        return self.save_playlist(playlist_name, tracks)
    
    def add_to_playlist(self, playlist_name, track_path):
        """Add a track to a playlist.
        
        Args:
            playlist_name (str): Name of the playlist
            track_path (str): Path to the track to add
            
        Returns:
            bool: True if added successfully, False otherwise
        """
        # Create playlist if it doesn't exist
        if playlist_name not in self.playlists:
            self.playlists[playlist_name] = {
                'tracks': [],
                'file': None  # Will be set when saved
            }
        
        # Check if the track exists
        if not os.path.exists(track_path):
            print(f"Warning: Track not found: {track_path}")
            return False
        
        # Add the track to the playlist
        self.playlists[playlist_name]['tracks'].append(track_path)
        
        # Save the updated playlist
        return self.save_playlist(playlist_name, self.playlists[playlist_name]['tracks'])
    
    def remove_from_playlist(self, playlist_name, track_index):
        """Remove a track from a playlist by index.
        
        Args:
            playlist_name (str): Name of the playlist
            track_index (int): Index of track to remove
            
        Returns:
            bool: True if removed successfully, False otherwise
        """
        if playlist_name not in self.playlists:
            print(f"Playlist not found: {playlist_name}")
            return False
        
        tracks = self.playlists[playlist_name]['tracks']
        
        if not 0 <= track_index < len(tracks):
            print(f"Invalid track index: {track_index}")
            return False
        
        # Remove the track
        tracks.pop(track_index)
        
        # Save the updated playlist
        return self.save_playlist(playlist_name, tracks)
    
    def rename_playlist(self, old_name, new_name):
        """Rename a playlist.
        
        Args:
            old_name (str): Current name of the playlist
            new_name (str): New name for the playlist
            
        Returns:
            bool: True if renamed successfully, False otherwise
        """
        if old_name not in self.playlists:
            print(f"Playlist not found: {old_name}")
            return False
        
        if new_name in self.playlists:
            print(f"Playlist already exists: {new_name}")
            return False
        
        # Get playlist info
        playlist_info = self.playlists.pop(old_name)
        
        # Save under new name
        return self.save_playlist(new_name, playlist_info['tracks'])