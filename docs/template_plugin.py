# plugins/your_plugin_name.py
import time
import os
import tempfile
from plugins import BasePlugin

class Plugin(BasePlugin):
    """
    Your Plugin Name and Description
    
    Replace this with a description of what your plugin does.
    This will be displayed in help documentation.
    """
    
    def __init__(self, player):
        """
        Initialize your plugin
        
        REQUIRED: All plugins must implement this method
        """
        # Always call the parent class constructor first
        super().__init__(player)
        
        # Basic plugin properties - REQUIRED
        self.name = "Your Plugin Name"  # User-friendly display name 
        self.command_name = player.env("YOUR_PLUGIN_CMD", default="yourplugin")  # Command used in CLI
        self.paginate_commands = ['search', 'list']  # Commands that will use pagination
        
        # Plugin-specific initialization
        # Add your own properties here
        self.current_tracks = []
        self.current_track = None
        self.current_track_index = None
        
        # Optional: Create temp directory for downloads/cache if needed
        self.temp_dir = tempfile.mkdtemp()
        
        # Optional: Set up persistent storage directory
        self.data_dir = player.env("YOUR_PLUGIN_DATA_DIR", default="your_plugin_data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Initialize your service/API connections here
        try:
            # Your initialization code
            # Example: self.api = YourServiceAPI(player.env("API_KEY"))
            
            # IMPORTANT: Set initialized to True ONLY if everything is ready
            self.initialized = True
        except Exception as e:
            print(f"Error initializing plugin: {e}")
            self.initialized = False
    
    # ========== REQUIRED METHODS ==========
    
    def command_help(self):
        """
        Return help text for your plugin's commands
        
        REQUIRED: All plugins must implement this method
        """
        if not self.is_available():
            return "Your plugin is not available"
        
        help_text = """
Available commands:
  play [args]    - Play or resume playback
  pause          - Pause playback
  stop           - Stop playback
  next           - Skip to next track
  prev           - Go to previous track
  search <query> - Search for media
  list           - List available media
  volume <0-100> - Set playback volume
  
  # Add your custom commands here
"""
        return help_text
    
    def _play_impl(self, args):
        """
        Play implementation - handle the play command
        
        REQUIRED: All plugins must implement this method
        
        This method is called when the user runs: yourplugin play [args]
        It should start playback or resume paused playback.
        """
        # IMPORTANT: Ensure exclusive playback before starting
        self.player.plugin_manager.ensure_exclusive_playback(self.plugin_id)
        
        try:
            # No arguments - resume current playback if available
            if not args:
                if self.current_track:
                    # Resume logic here
                    return True
                else:
                    print("No track loaded to play")
                    return False
            
            # === Handle different argument types from pagination and CLI ===
            
            # 1. Direct pagination selection (display_text, item_id, metadata)
            if isinstance(args, tuple) and len(args) == 3:
                display_text, item_id, metadata = args
                # Play the item using the ID and metadata
                return True
                
            # 2. Pagination selection wrapped in a list
            if isinstance(args, list) and len(args) == 1 and isinstance(args[0], tuple):
                display_text, item_id, metadata = args[0]
                # Play the item using the ID and metadata
                return True
                
            # 3. Direct index from pagination
            if isinstance(args, list) and len(args) == 1 and isinstance(args[0], int):
                index = args[0]
                if self.current_tracks and 0 <= index < len(self.current_tracks):
                    # Play the track at the specified index
                    return True
                else:
                    print(f"Invalid index: {index}")
                    return False
                
            # 4. Index as string from command line
            if isinstance(args, list) and len(args) == 1 and isinstance(args[0], str) and args[0].isdigit():
                index = int(args[0])
                if self.current_tracks and 0 <= index < len(self.current_tracks):
                    # Play the track at the specified index
                    return True
                else:
                    print(f"Invalid index: {index}")
                    return False
                    
            # 5. Search term or other string arguments
            search_term = " ".join(args) if isinstance(args, list) else args
            print(f"Searching for: {search_term}")
            # Your search and play logic here
            
            return False  # Replace with your implementation
        except Exception as e:
            print(f"Error playing: {e}")
            return False
    
    def _pause_impl(self, args):
        """
        Pause playback implementation
        
        REQUIRED: All plugins must implement this method
        
        This method is called when the user runs: yourplugin pause
        """
        if not self.current_track:
            print("Nothing is currently playing")
            return False
            
        try:
            # Your pause implementation here
            # For streaming services: return self.api.pause()
            # For local audio: return self.pause_audio()
            return False  # Replace with your implementation
        except Exception as e:
            print(f"Error pausing: {e}")
            return False
    
    def _stop_impl(self, args):
        """
        Stop playback implementation
        
        REQUIRED: All plugins must implement this method
        
        This method is called when the user runs: yourplugin stop
        """
        if not self.current_track:
            return True  # Nothing to stop
            
        try:
            # Your stop implementation here
            # For streaming services: return self.api.stop()
            # For local audio: return self.stop_audio()
            return False  # Replace with your implementation
        except Exception as e:
            print(f"Error stopping: {e}")
            return False
    
    def _set_volume_impl(self, volume):
        """
        Set volume level implementation
        
        REQUIRED: All plugins must implement this method
        
        This method is called when the user runs: yourplugin volume <0-100>
        volume parameter will be an integer between 0-100
        """
        try:
            # Your volume control implementation here
            # For streaming services: return self.api.set_volume(volume)
            # For local audio: return self.set_audio_volume(volume / 100.0)
            print(f"Volume set to {volume}%")
            return False  # Replace with your implementation
        except Exception as e:
            print(f"Error setting volume: {e}")
            return False
    
    def update_playback_info(self):
        """
        Update the plugin manager with current playback info
        
        REQUIRED: All plugins must implement this method
        
        This method should get the current playback state and update the plugin manager.
        """
        if not self.current_track:
            return
            
        try:
            # Build standardized playback info
            # For API services: get status from API
            # For local playback: use helper methods
            
            playback_info = {
                'track_name': "Unknown",  # Replace with actual track name
                'artist': "Unknown",      # Replace with actual artist
                'album': None,            # Replace with actual album if available
                'position': 0,            # Replace with actual position in seconds
                'duration': 0,            # Replace with actual duration in seconds
                'state': 'PLAYING'        # 'PLAYING', 'PAUSED', or 'STOPPED'
            }
            
            # Update the plugin manager
            self.update_playback_state_from_info(playback_info)
        except Exception as e:
            print(f"Error updating playback info: {e}")
    
    def get_current_playback(self):
        """
        Get current playback information
        
        REQUIRED: All plugins must implement this method
        
        Returns a PlaybackInfo dict or None if nothing is playing
        """
        if not self.current_track:
            return None
            
        try:
            # Return current playback info in standard format
            return {
                'track_name': "Unknown",  # Replace with actual track name
                'artist': "Unknown",      # Replace with actual artist
                'album': None,            # Replace with actual album if available
                'position': 0,            # Replace with actual position in seconds
                'duration': 0,            # Replace with actual duration in seconds
                'is_playing': False       # Replace with actual playing state
            }
        except Exception as e:
            print(f"Error getting current playback: {e}")
            return None
    
    def play_track(self, track_data):
        """
        Play a track selected from search results or listing
        
        REQUIRED: All plugins must implement this method
        
        This is called with the selection from pagination
        """
        try:
            # Unpack the track data (format from pagination system)
            display_text, track_id, metadata = track_data
            
            # IMPORTANT: Ensure exclusive playback before starting
            self.player.plugin_manager.ensure_exclusive_playback(self.plugin_id)
            
            print(f"Playing: {display_text}")
            
            # Your logic to play the selected track
            # Update current_track and other state variables
            
            return False  # Replace with your implementation
        except Exception as e:
            print(f"Error playing track: {e}")
            return False
    
    # ========== OPTIONAL METHODS ==========
    # These methods are optional but recommended for a complete plugin
    
    def _next_impl(self, args):
        """
        Skip to next track implementation
        
        OPTIONAL: Implement if your plugin supports playlists/queues
        
        This method is called when the user runs: yourplugin next
        """
        if not self.current_tracks or self.current_track_index is None:
            print("No playlist loaded or no current track")
            return False
            
        try:
            next_index = (self.current_track_index + 1) % len(self.current_tracks)
            # Your logic to play the next track
            return False  # Replace with your implementation
        except Exception as e:
            print(f"Error going to next track: {e}")
            return False
    
    def _prev_impl(self, args):
        """
        Go to previous track implementation
        
        OPTIONAL: Implement if your plugin supports playlists/queues
        
        This method is called when the user runs: yourplugin prev
        """
        if not self.current_tracks or self.current_track_index is None:
            print("No playlist loaded or no current track")
            return False
            
        try:
            prev_index = (self.current_track_index - 1) % len(self.current_tracks)
            # Your logic to play the previous track
            return False  # Replace with your implementation
        except Exception as e:
            print(f"Error going to previous track: {e}")
            return False
    
    def search(self, args):
        """
        Search for media
        
        OPTIONAL: Add to self.paginate_commands if implementing this
        
        This method is called when the user runs: yourplugin search <query>
        Returns: List of tuples for pagination (display_text, item_id, metadata)
        """
        if not args:
            print(f"Usage: {self.command_name} search <query>")
            return []
            
        query = " ".join(args)
        print(f"Searching for: {query}")
        
        try:
            # Your search implementation here
            # Example: results = self.api.search(query)
            
            # Format results for pagination system
            display_items = []
            # Example:
            # for i, item in enumerate(results):
            #     display_items.append((
            #         f"{item['title']} - {item.get('artist', 'Unknown')}",
            #         item['id'],  # or i if using index
            #         item  # metadata or subset of item data
            #     ))
            
            # Return items for pagination
            return display_items
        except Exception as e:
            print(f"Error searching: {e}")
            return []
    
    def list(self, args):
        """
        List available media
        
        OPTIONAL: Add to self.paginate_commands if implementing this
        
        This method is called when the user runs: yourplugin list [args]
        Returns: List of tuples for pagination (display_text, item_id, metadata)
        """
        try:
            # Your listing implementation here
            # Example: items = self.api.get_items()
            
            # Format items for pagination
            display_items = []
            # Example:
            # for i, item in enumerate(items):
            #     display_items.append((
            #         f"{item['title']} - {item.get('artist', 'Unknown')}",
            #         item['id'],  # or i if using index
            #         item  # metadata or subset of item data
            #     ))
            
            # Return items for pagination
            return display_items
        except Exception as e:
            print(f"Error listing items: {e}")
            return []
    
    # ========== EVENT HANDLERS ==========
    # These methods are optional but useful for plugin coordination
    
    def on_play(self, data):
        """
        Called when a track starts playing
        
        OPTIONAL: Implement to handle system play events
        
        Useful to pause your plugin when another plugin starts playing
        """
        # If another plugin starts playing, we may want to pause/stop
        if data.get('plugin_id') != self.plugin_id and self._is_playing():
            self.stop([])
    
    def on_pause(self, data):
        """
        Called when playback is paused
        
        OPTIONAL: Implement to handle system pause events
        """
        pass
    
    def on_stop(self, data):
        """
        Called when playback is stopped
        
        OPTIONAL: Implement to handle system stop events
        """
        pass
    
    def on_shutdown(self, data):
        """
        Called when the player is shutting down
        
        OPTIONAL but RECOMMENDED: Implement to clean up resources
        """
        # Stop any active playback
        self.stop([])
        
        # Clean up resources
        # Example: self.api.disconnect()
        
        # Clean up temp files and directories
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, file))
                    except:
                        pass
                os.rmdir(self.temp_dir)
        except Exception as e:
            print(f"Warning: Could not clean up temp directory: {e}")
    
    # ========== CUSTOM METHODS ==========
    # Add your own custom methods below
    
    # Helper method example - you can add your own helpers
    def _play_item(self, item_id, metadata):
        """
        Internal helper to play an item by ID
        
        This is an example of a helper method you might add
        """
        try:
            # Your implementation to play an item using its ID and metadata
            # Example for API service: self.api.play_item(item_id)
            # Example for local file: self.play_audio_file(metadata['file_path'])
            
            # Update current track info
            self.current_track = metadata
            
            # Update playback state
            self.update_playback_info()
            
            return False  # Replace with your implementation
        except Exception as e:
            print(f"Error playing item: {e}")
            return False
    
    # Add as many custom methods as needed for your plugin's functionality