#Player
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import time
import threading
import pygame
import random
from enum import Enum
from typing import Dict, List, Callable, Any
from modules.media_handler import MediaHandler
from modules.playlist_handler import PlaylistHandler
from modules.plugin_manager import PluginManager

from modules.logging_utils import log_function_call, app_logger as log

class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
    
    def subscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            self._listeners[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable) -> bool:
        with self._lock:
            if event_type in self._listeners and callback in self._listeners[event_type]:
                self._listeners[event_type].remove(callback)
                return True
            return False
    
    def publish(self, event_type: str, data: Any = None, callback: Callable = None, 
                callback_args: tuple = None, callback_kwargs: dict = None) -> None:
        callback_args = callback_args or ()
        callback_kwargs = callback_kwargs or {}
            
        with self._lock:
            if event_type in self._listeners:
                for listener in self._listeners[event_type]:
                    threading.Thread(
                        target=self._safe_callback_execution,
                        args=(listener, data)
                    ).start()
                    
        if callback:
            threading.Thread(
                target=lambda: callback(*callback_args, **callback_kwargs)
            ).start()
    
    def _safe_callback_execution(self, callback, data):
        try:
            callback(data)
        except Exception as e:
            print(f"Error in event callback: {e}")

class PlayerState(Enum):
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2

def clear_screen():
    # For Windows
    if os.name == 'nt':
        os.system('cls')
    # For Mac and Linux
    else:
        os.system('clear')
clear_screen()

class MusicPlayer:
    """Core music player functionality"""   
    STATE_CHANGED = 'state_changed'
    SOURCE_CHANGED = 'source_changed'
    TRACK_CHANGED = 'track_changed'
    POSITION_CHANGED = 'position_changed'
    VOLUME_CHANGED = 'volume_changed'          
    def __init__(self, env):
        """Initialize the music player"""
        self.MUSIC_LIBRARY_PATH = env("MUSIC_LIBRARY_PATH", default=None)
        self.SCAN_SUBDIRECTORIES = env("SCAN_SUBDIRECTORIES", default=False)
        self.DEFAULT_SORT = env("DEFAULT_SORT", default="name")
        self.NOW_PLAYING_DEFAULT = env("NOW_PLAYING_DEFAULT", default=False)
        self.PLAYLISTS_PATH = env("PLAYLISTS_PATH", default="playlists")
        self.PLUGINS_PATH = env("PLUGINS_PATH", default="plugins")
        self.env = env
        self.event_bus = EventBus()
        self.media_handler = MediaHandler()  
        pygame.init()  # Only initialize other pygame components
        
        # Player state
        self.state = PlayerState.STOPPED
        self.current_track = None
        self.media = []
        self.playlist = []
        self.current_index = 0
        self.current_playlist_name = None
        self.playback_info = {
            'source': 'local',  # 'local' or plugin name
            'track_name': None,
            'artist': None,
            'album': None,
            'genre': None,
            'position': 0,
            'duration': 0,
            'bitrate': None,
            'year': None,
            'state': 'STOPPED',  # 'STOPPED', 'PLAYING', 'PAUSED'
            'plugin_instance': None  # Reference to the active plugin instance
        }
        
        # Set initial volume
        volume_setting = env("DEFAULT_VOLUME", default=70)
        self.volume = volume_setting / 100.0 if volume_setting > 1 else volume_setting
        self.media_handler.set_audio_volume(self.volume)  # Use new method
        
        # Track playback details
        self.current_track_length = 0
        self.track_start_time = 0
        
        # Initialize other handlers
        self.playlist_handler = PlaylistHandler(playlists_dir=self.PLAYLISTS_PATH)
        self.user_playlists = self.playlist_handler.scan_playlists()
        # Add local media
        
        # log.info("initialize plugin manager")
        # Create the plugin manager - ONLY ONCE with a reference to this player
        self.plugin_manager = PluginManager(player_instance=self)
        self.plugin_manager.set_active_plugin('local')
        # log.info("scan plugins")
        # Scan plugins directory to find available plugins
        self.plugins_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), self.PLUGINS_PATH)
        self.available_plugins = self.plugin_manager.scan_plugin_directory(self.plugins_dir)
        # log.info("load plugins")
        # Load enabled plugins if auto-load is enabled
        self.plugins = {}
        if self.plugin_manager.settings['auto_load_plugins']:
            self.load_plugins()
        
        # Event handling thread
        self.running = True
        self.shuffle_mode = True if self.DEFAULT_SORT.lower() == "random" else False
        self.original_playlist_order = []
        
        # Start event loop
        self._start_event_loop()

        # log.info("load music library")
        # Load music library if specified
        # if self.MUSIC_LIBRARY_PATH:
        #     self.MUSIC_LIBRARY_PATH = os.path.expanduser("~")
        if self.MUSIC_LIBRARY_PATH:
            # Check if MUSIC_LIBRARY_PATH contains commas
            if "," in self.MUSIC_LIBRARY_PATH:
                # Split by comma and create a list of paths
                paths = [path.strip() for path in self.MUSIC_LIBRARY_PATH.split(",")]
            else:
                # Create a list with a single element
                paths = [self.MUSIC_LIBRARY_PATH]
        else:
            # Default to home directory if no path is specified
            paths = [os.path.expanduser("~")]

        # self.media_handler.add_media_location(self.MUSIC_LIBRARY_PATH)
        self.media_handler.add_media_location(paths)
        self.media_handler.update_media_index()
        # self.load_media(self.MUSIC_LIBRARY_PATH)
        for path in paths:
            self.load_media(path)
        if self.media:
            self.user_playlists["Local Media"]["tracks"] = self.media

        if self.media:
            self.user_playlists["Local Media"] = {
                "tracks": self.media,
                "file": None  # This is an in-memory playlist
            }
            
            # Automatically load Local Media as the active playlist
            self.playlist = self.media.copy()
            self.current_playlist_name = "Local Media"
            
            # Apply sorting if shuffle is enabled
            if self.shuffle_mode:
                # Store original playlist order
                self.original_playlist_order = self.playlist.copy()
                # Shuffle the playlist
                random.shuffle(self.playlist)
            
            # Notify plugins
            self.event_bus.publish('on_playlist_loaded', {'playlist': self.playlist})
        
    def set_player_state(self, state):
        """Update both the enum state and the playback_info state consistently"""
        old_state = self.state
        
        # Update the enum state
        self.state = state
        
        # Get the string representation for playback_info
        state_str = {
            PlayerState.PLAYING: 'PLAYING',
            PlayerState.PAUSED: 'PAUSED',
            PlayerState.STOPPED: 'STOPPED'
        }[state]
        
        # Update playback_info and trigger events
        if old_state != state:
            self.update_playback_info({'state': state_str})

    def update_playback_info(self, info):
        """Update playback information and publish relevant events"""
        # Track what fields are changing
        state_changed = False
        source_changed = False
        track_changed = False
        
        # Check for specific changes
        if 'state' in info and info['state'] != self.playback_info['state']:
            state_changed = True
            
            # If state string is changing, update the enum state too
            state_map = {
                'PLAYING': PlayerState.PLAYING,
                'PAUSED': PlayerState.PAUSED,
                'STOPPED': PlayerState.STOPPED
            }
            if info['state'] in state_map and self.state != state_map[info['state']]:
                self.state = state_map[info['state']]
        
        if 'source' in info and info['source'] != self.playback_info['source']:
            source_changed = True
                
        if 'track_name' in info and info['track_name'] != self.playback_info['track_name']:
            track_changed = True
        
        # Update the playback info
        for key, value in info.items():
            if key in self.playback_info:
                self.playback_info[key] = value
        
        # Publish relevant events
        if state_changed:
            self.event_bus.publish(self.STATE_CHANGED, {
                'previous_state': self.playback_info['state'],
                'new_state': info['state'],
                'source': self.playback_info['source']
            })
        
        if source_changed:
            self.event_bus.publish(self.SOURCE_CHANGED, {
                'previous_source': self.playback_info['source'],
                'new_source': info['source']
            })
                
        if track_changed:
            self.event_bus.publish(self.TRACK_CHANGED, {
                'track_name': info['track_name'],
                'artist': self.playback_info.get('artist'),
                'album': self.playback_info.get('album')
            })

    def _start_event_loop(self):
        """Start the event handling thread"""
        def _event_loop():
            """Background thread for handling events like track ending."""
            while self.running:
                # Only check pygame status if local playback is active
                if self.plugin_manager.get_active_plugin() == 'local' and self.state == PlayerState.PLAYING and not pygame.mixer.music.get_busy():
                    # Track finished playing
                    old_state = self.state
                    self.state = PlayerState.STOPPED
                    
                    # Publish state change event
                    self.update_playback_info({'state': 'STOPPED'})
                    
                    # Auto-play next track
                    if self.playlist and len(self.playlist) > 0:
                        # Move to next track
                        if self.shuffle_mode:
                            self.current_index = (random.randint(0, len(self.playlist)) +1) % len(self.playlist)
                        else:
                            self.current_index = (self.current_index + 1) % len(self.playlist)
                        
                        # Update the current track and publish track change event
                        old_track = self.current_track
                        self.current_track = self.playlist[self.current_index]
                        
                        # Only publish track change if it's a different track
                        if old_track != self.current_track:
                            self.event_bus.publish(self.TRACK_CHANGED, {
                                'previous_track': old_track,
                                'new_track': self.current_track
                            })
                        
                        # Play it
                        self.play()
                time.sleep(0.1)
        
        # Start the event thread
        self.event_thread = threading.Thread(target=_event_loop)
        self.event_thread.daemon = True
        self.event_thread.start()


    @log_function_call
    def prepare_plugin_playback(self, plugin_name):
        """
        Prepare for a plugin to start playback by pausing any currently playing sources
        and setting the plugin as active.
        """
        # First notify all sources that a new source is about to play
        self.event_bus.publish(self.SOURCE_CHANGED, {
            'previous_source': self.plugin_manager.get_active_plugin(),
            'new_source': plugin_name
        })
        
        # For backward compatibility
        self.event_bus.publish('prepare_for_playback', {'new_source': plugin_name})
        
        # Let the plugin manager handle the source switching
        return self.plugin_manager.ensure_exclusive_playback(plugin_name)

    def load_plugins(self):
        """Load enabled plugins from the plugins directory."""
        loaded_count = self.plugin_manager.load_enabled_plugins(self.plugins_dir, self)
        self.plugins = self.plugin_manager.get_all_plugins()
        return loaded_count
    
    def enable_plugin(self, plugin_name):
        """Enable a specific plugin."""
        if self.plugin_manager.enable_plugin(plugin_name):
            # Load the plugin if it was enabled successfully
            plugin_info = self.plugin_manager.available_plugins.get(plugin_name)
            if plugin_info and not plugin_info['loaded']:
                self.plugin_manager.load_plugin(plugin_name, plugin_info['path'], self)
                # Update local plugins dictionary
                self.plugins = self.plugin_manager.get_all_plugins()
            return True
        return False
    
    def disable_plugin(self, plugin_name):
        """Disable a specific plugin."""
        if self.plugin_manager.disable_plugin(plugin_name):
            # Update local plugins dictionary
            self.plugins = self.plugin_manager.get_all_plugins()
            return True
        return False
    
    def set_auto_load_plugins(self, enabled):
        """Set whether plugins should be automatically loaded."""
        return self.plugin_manager.set_auto_load(enabled)
    
    def get_plugin_settings(self):
        """Get current plugin settings."""
        return self.plugin_manager.settings
    
    def scan_plugins(self):
        """Scan the plugins directory for available plugins."""
        self.available_plugins = self.plugin_manager.scan_plugin_directory(self.plugins_dir)
        return self.available_plugins
    
    def load_media(self, directory):
        """Load all music files from a directory."""
        media = []
        # Add the directory to our index if it's not already there
        if self.media_handler.add_media_location(directory):
            # Update the index to scan the new location
            self.media_handler.update_media_index(force=True)
        
        # For backward compatibility, also use the direct load method
        direct_files = self.media_handler.load_media_from_directory(
            directory, 
            recursive=self.SCAN_SUBDIRECTORIES
        )
        
        # # Get all tracks from the media handler index
        # indexed_files = self.media_handler.get_all_indexed_tracks(
        #     sort_method=self.DEFAULT_SORT.lower(),
        #     shuffle=(self.DEFAULT_SORT.lower() == 'random')
        # )
        
        # Merge both sets of files (indexed and direct)
        # media = list(set(direct_files + indexed_files))
        media = list(direct_files)
                
        # Print loading summary
        print(f"Loaded {len(media)} tracks from {directory}")
        self.media.extend(media)
        
    def play(self):
        """Start or resume playback."""
        # First ensure this source (local) has exclusive playback
        self.plugin_manager.ensure_exclusive_playback('local')
        
        # Now proceed with normal play logic based on current state
        if self.state == PlayerState.STOPPED:
            if self.playlist and self.current_index < len(self.playlist):
                self.current_track = self.playlist[self.current_index]
                # print(f"Playing track: {os.path.basename(self.current_track)}")
                
                # Get track duration before playing
                self.current_track_length = self.media_handler.get_track_duration(self.current_track)
                
                # Use MediaHandler method to play
                success, temp_file = self.media_handler.play_audio(self.current_track)
                if not success:
                    print(f"Cannot play {os.path.basename(self.current_track)}: format not supported")
                    return
                
                self.track_start_time = time.time()
                self.state = PlayerState.PLAYING
                
                # Update playback info and publish state events
                self.update_playback_info({
                    'state': 'PLAYING',
                    'track_name': os.path.basename(self.current_track),
                    'source': 'local'
                })
                
                # Make sure plugin manager knows local is the active source
                self.plugin_manager.set_active_plugin('local')
                
                # Update play stats
                self.media_handler.update_play_stats(self.current_track)
                
                # For backward compatibility, still publish the on_play event
                self.event_bus.publish('on_play', {'track': self.current_track})
            else:
                print("No tracks in playlist")
        elif self.state == PlayerState.PAUSED:
            self.media_handler.resume_audio()
            self.state = PlayerState.PLAYING
            
            # Update playback state and publish state event
            self.update_playback_info({'state': 'PLAYING'})
                
    def get_current_playback(self):
        """
        Get information about what's currently playing, regardless of source.
        
        Returns:
            dict: A dictionary with current playback information
        """
        # If it's local playback and we're playing, update the position
        current_playback = self.playback_info.copy()
        if self.state == PlayerState.PLAYING:
            if current_playback['source'] == 'local':
                #! Prioritizing meta tags, else getting from media handler (index then direct check)
                metadata = self.media_handler.get_metadata_from_tags(self.current_track) 
                data = self.media_handler.get_metadata_from_file(self.current_track)
                elapsed = time.time() - self.track_start_time   
                #! Get metadata if exists, otherwise use local data
                track_name = (metadata and metadata.get('title')) or (data and data.get('track_name')) or None
                duration = (metadata and metadata.get('duration')) or (data and data.get('duration')) or None
                # Get metadata if exists, local data on this does not exist
                artist = metadata['artist'] if metadata and 'artist' in metadata else None
                album = metadata['album'] if metadata and 'album' in metadata else None
                genre = metadata['genre'] if metadata and 'genre' in metadata else None
                bitrate = metadata['bitrate'] if metadata and 'bitrate' in metadata else None
                year = metadata['year'] if metadata and 'year' in metadata else None

                self.update_playback_info({
                                'track_name': track_name,
                                'position': min(elapsed, duration),
                                'duration': duration,
                                'artist': artist,
                                'album': album,
                                'genre': genre,
                                'bitrate': bitrate,
                                'year': year,
                                'source': 'local',
                                'state': 'PLAYING' 
                            })
            else:
                # Use the plugin manager to get current playback info
                current_playback = self.plugin_manager.get_playback_info()
        
            return current_playback
        return self.playback_info

    def pause(self):
        """Pause playback."""
        # Check if we're controlling local playback or a plugin
        active_plugin = self.plugin_manager.get_active_plugin()
        
        if active_plugin == 'local' and self.state == PlayerState.PLAYING:
            self.media_handler.pause_audio()
            self.state = PlayerState.PAUSED
            
            # Update playback info and publish state event
            self.update_playback_info({'state': 'PAUSED'})
            
            # For backward compatibility
            self.event_bus.publish('on_pause', {})
            
        elif active_plugin != 'local':
            # Let the plugin handle it
            plugin = self.plugins.get(active_plugin)
            if plugin and hasattr(plugin, 'pause'):
                plugin.pause([])
    
    def stop(self):
        """Stop playback."""
        # Check if we're controlling local playback or a plugin
        active_plugin = self.plugin_manager.get_active_plugin()
        
        if active_plugin == 'local':
            self.media_handler.stop_audio()
            self.state = PlayerState.STOPPED
            
            # Update playback info and publish state event
            self.update_playback_info({'state': 'STOPPED'})
            
            # For backward compatibility
            self.event_bus.publish('on_stop', {})
            
        elif active_plugin != 'local':
            # Let the plugin handle it
            plugin = self.plugins.get(active_plugin)
            if plugin and hasattr(plugin, 'stop'):
                plugin.stop([])
            elif plugin and hasattr(plugin, 'pause'):
                # If no stop method, try pause as fallback
                plugin.pause([])
    
    def next_track(self):
        """Play the next track in the playlist."""
        # Check if any plugin is currently active
        active_plugin = self.plugin_manager.get_active_plugin()
        
        if active_plugin != 'local':
            # Let the active plugin handle next track
            plugin = self.plugins.get(active_plugin)
            if plugin and hasattr(plugin, 'next'):
                plugin.next([])
                return
        
        # Local playback handling
        if self.playlist:
            self.stop()
            if self.shuffle_mode:
                self.current_index = (random.randint(0, len(self.playlist)) +1) % len(self.playlist)
            else:
                self.current_index = (self.current_index + 1) % len(self.playlist)
            self.play()

    def previous_track(self):
        """Play the previous track in the playlist."""
        # Check if any plugin is currently active
        active_plugin = self.plugin_manager.get_active_plugin()
        
        if active_plugin != 'local':
            # Let the active plugin handle previous track
            plugin = self.plugins.get(active_plugin)
            if plugin and hasattr(plugin, 'prev'):
                plugin.prev([])
                return
        
        # Local playback handling
        if self.playlist:
            self.stop()
            self.current_index = (self.current_index - 1) % len(self.playlist)
            self.play()
    
    def get_playback_position(self):
        """Get the current playback position in seconds."""
        # Check if we're getting position from a plugin
        active_plugin = self.plugin_manager.get_active_plugin()
        if active_plugin != 'local':
            # Get from plugin manager's cached info
            return self.plugin_manager.get_playback_info()['position']
        
        # Local playback handling
        if self.state == PlayerState.STOPPED:
            return 0
        
        # Get position from MediaHandler
        pos = self.media_handler.get_audio_position()  # Use new method
        if pos > 0:  # If valid position
            return pos / 1000.0  # Convert from ms to seconds
            
        # Fallback to time-based tracking
        elapsed = time.time() - self.track_start_time
        return elapsed
    
    def get_status(self):
        """Get the current player status."""
        # Get current playback info from plugin manager
        playback = self.plugin_manager.get_playback_info()
        
        # Build status dictionary
        status = {
            'state': playback['state'],
            'source': playback['source'],
            'current_track': playback['track_name'],
            'artist': playback['artist'],
            'album': playback['album'],
            'playlist_length': len(self.playlist),
            'current_index': self.current_index,
            'position': playback['position'],
            'duration': playback['duration'],
            'volume': self.volume,
            'shuffle': self.shuffle_mode,
            'plugins_enabled': len(self.plugins),
            'plugins_available': len(self.available_plugins),
            'auto_load_plugins': self.plugin_manager.settings['auto_load_plugins']
        }
        
        return status
    
    # def _notify_plugins(self, event_name, data):
    #     """Notify all plugins about an event."""
    #     for plugin_name, plugin in self.plugins.items():
    #         if hasattr(plugin, event_name):
    #             try:
    #                 getattr(plugin, event_name)(data)
    #             except Exception as e:
    #                 print(f"Error in plugin {plugin_name} handling {event_name}: {e}")
    
    def shutdown(self):
        """Clean shutdown of the player."""
        self.running = False
        
        # Get the current active plugin before stopping
        active_plugin = self.plugin_manager.get_active_plugin()
        
        # Stop all playback
        try:
            self.stop()
        except Exception as e:
            print(f"Warning when stopping playback: {e}")
        
        # Set local as active to prevent plugin conflicts during shutdown
        self.plugin_manager.set_active_plugin('local')
        
        # Notify all plugins about shutdown using event bus
        self.event_bus.publish('on_shutdown', {})
        
        # Clean up media handler
        try:
            self.media_handler.cleanup()
        except Exception as e:
            print(f"Warning cleaning up media handler: {e}")
        
        try:
            pygame.quit()
        except Exception as e:
            print(f"Warning quitting pygame: {e}")

    def set_volume(self, volume):
        """Set the volume level (0.0 to 1.0)."""
        old_volume = self.volume
        self.volume = max(0.0, min(1.0, volume))
        self.media_handler.set_audio_volume(self.volume)
        
        # Publish volume changed event
        self.event_bus.publish(self.VOLUME_CHANGED, {
            'previous_volume': old_volume,
            'new_volume': self.volume
        })
        
        # For backward compatibility
        self.event_bus.publish('on_volume_change', {'volume': self.volume})
        
        return self.volume

    def scan_playlists(self):
        """Scan for and load user playlists from the playlists directory."""
        self.user_playlists = self.playlist_handler.scan_playlists()
        return self.user_playlists

    def save_playlist(self, playlist_name, tracks, file_name=None):
        """Save a playlist to a file."""
        result = self.playlist_handler.save_playlist(playlist_name, tracks, file_name)
        if result:
            self.user_playlists = self.playlist_handler.playlists
        return result

    def load_playlist(self, playlist_name):
        """Load a user playlist into the active playlist."""
        tracks = self.playlist_handler.get_playlist(playlist_name)
        if not tracks:
            print(f"Playlist not found or empty: {playlist_name}")
            return False
        
        # Set the tracks from the playlist
        self.playlist = tracks.copy()
        self.current_index = 0
        self.current_playlist_name = playlist_name
        
        # Apply sorting if shuffle is enabled
        # if self.shuffle_mode:
        #     # Store original playlist order
        #     self.original_playlist_order = self.playlist.copy()
        #     # Shuffle the playlist
        #     random.shuffle(self.playlist)
        
        # Notify plugins
        self.event_bus.publish('on_playlist_loaded', {'playlist': self.playlist})
        
        print(f"\nLoaded playlist: {playlist_name} ({len(self.playlist)} tracks)")
        return True

    def save_current_as_playlist(self, playlist_name):
        """Save the current playlist as a user playlist."""
        if not self.playlist:
            print("Current playlist is empty")
            return False
        
        result = self.playlist_handler.save_playlist(playlist_name, self.playlist)
        if result:
            self.user_playlists = self.playlist_handler.playlists
        return result

    def add_to_playlist(self, playlist_name, track_path):
        """Add a track to a playlist."""
        result = self.playlist_handler.add_to_playlist(playlist_name, track_path)
        
        # If this is the current playlist, update it
        if result and self.current_playlist_name == playlist_name:
            # Add to the current playlist too
            # if self.shuffle_mode:
            #     # Add to original order
            #     self.original_playlist_order.append(track_path)
            #     # Add to a random position in the current playlist
            #     insert_idx = random.randint(0, len(self.playlist))
            #     self.playlist.insert(insert_idx, track_path)
            # else:
            self.playlist.append(track_path)
        
        return result

    def remove_from_playlist(self, playlist_name, track_index):
        """Remove a track from a playlist by index."""
        # Get the track before removal (for updating current playlist)
        track = None
        if playlist_name in self.user_playlists:
            tracks = self.user_playlists[playlist_name]['tracks']
            if 0 <= track_index < len(tracks):
                track = tracks[track_index]
        
        # Remove from playlist handler
        result = self.playlist_handler.remove_from_playlist(playlist_name, track_index)
        
        # If this is the current playlist, update it
        if result and track and self.current_playlist_name == playlist_name:
            # if self.shuffle_mode:
            #     # Remove from original order
            #     try:
            #         self.original_playlist_order.remove(track)
            #     except ValueError:
            #         pass
            #     # Remove from current playlist
            #     try:
            #         self.playlist.remove(track)
            #     except ValueError:
            #         pass
            # else:
            if track_index < self.current_index:
                self.current_index -= 1
            elif track_index == self.current_index:
                # If removing current track, stop playback
                self.stop()
            self.playlist.pop(track_index)
        
        return result

    def rename_playlist(self, old_name, new_name):
        """Rename a playlist."""
        result = self.playlist_handler.rename_playlist(old_name, new_name)
        
        # Update current playlist name if it was renamed
        if result and self.current_playlist_name == old_name:
            self.current_playlist_name = new_name
        
        return result
    
    def toggle_shuffle(self):
        """Toggle shuffle mode on/off."""
        self.shuffle_mode = not self.shuffle_mode
        
        # # Only affects local playback
        # if self.playlist:
        #     if self.shuffle_mode:
        #         # Store original playlist order if not already stored
        #         if not self.original_playlist_order:
        #             self.original_playlist_order = self.playlist.copy()
                
        #         # Remember current track
        #         current_track = self.playlist[self.current_index] if self.current_index < len(self.playlist) else None
                
        #         # Shuffle the playlist
        #         import random
        #         random.shuffle(self.playlist)
                
        #         # Try to keep the current track as current
        #         if current_track:
        #             try:
        #                 self.current_index = self.playlist.index(current_track)
        #             except ValueError:
        #                 # Current track not found in shuffled playlist
        #                 self.current_index = 0
        #     else:
        #         # Restore original playlist order
        #         if self.original_playlist_order:
        #             # Remember current track
        #             current_track = self.playlist[self.current_index] if self.current_index < len(self.playlist) else None
                    
        #             # Restore original order
        #             self.playlist = self.original_playlist_order.copy()
        #             self.original_playlist_order = []
                    
        #             # Try to keep the current track as current
        #             if current_track:
        #                 try:
        #                     self.current_index = self.playlist.index(current_track)
        #                 except ValueError:
        #                     # Current track not found in original playlist
        #                     self.current_index = 0
        
        # Notify plugins about shuffle mode change
        self.event_bus.publish('on_shuffle_change', {'shuffle': self.shuffle_mode})
        
        status = "enabled" if self.shuffle_mode else "disabled"
        return status

    def add_library_location(self, directory):
        """Add a new location to the media library.
        
        Args:
            directory (str): Path to the directory to add
            
        Returns:
            bool: True if successful, False if already indexed or not found
        """
        # Add to media handler
        if self.media_handler.add_media_location(directory):
            # Update the index
            self.media_handler.update_media_index(force=True)
            print(f"Added library location: {directory}")
            
            # # Refresh the playlist
            all_tracks = self.media_handler.get_all_indexed_tracks(
                sort_method=self.DEFAULT_SORT.lower(),
                # shuffle=self.shuffle_mode
            )
            
            # Update playlist with new tracks
            for track in all_tracks:
                if track not in self.playlist:
                    self.playlist.append(track)
            
            # # Apply sorting if needed
            # if self.DEFAULT_SORT.lower() == 'name':
            #     self.playlist.sort(key=lambda x: os.path.basename(x).lower())
            # elif self.DEFAULT_SORT.lower() == 'date':
            #     self.playlist.sort(key=lambda x: os.path.getmtime(x))
            # elif self.shuffle_mode:
            #     random.shuffle(self.playlist)
            
            # Notify plugins
            self.event_bus.publish('on_playlist_loaded', {'playlist': self.playlist})
            
            return True
        else:
            print(f"Location already indexed: {directory}")
            return False
    
    def remove_library_location(self, directory):
        """Remove a location from the media library.
        
        Args:
            directory (str): Path to the directory to remove
            
        Returns:
            bool: True if successful, False if not found
        """
        # Remove from media handler
        if self.media_handler.remove_media_location(directory):
            # Update the index
            self.media_handler.update_media_index(force=True)
            print(f"Removed library location: {directory}")
            
            # Get current tracks after removal
            current_tracks = self.media_handler.get_all_indexed_tracks()
            
            # Filter playlist to remove tracks that are no longer available
            # Keep track of whether current track is removed
            current_track_removed = False
            if self.current_track and self.current_track not in current_tracks:
                current_track_removed = True
            
            # Update playlist
            self.playlist = [track for track in self.playlist if track in current_tracks]
            
            # Stop playback if current track was removed
            if current_track_removed and self.state != PlayerState.STOPPED:
                self.stop()
                self.current_index = 0
            
            # Notify plugins
            self.event_bus.publish('on_playlist_loaded', {'playlist': self.playlist})
            
            return True
        else:
            print(f"Location not in index: {directory}")
            return False
    
    def get_library_locations(self):
        """Get all locations in the media library.
        
        Returns:
            list: List of indexed directory paths
        """
        return self.media_handler.get_media_locations()
    
    def search_library(self, query, limit=20):
        """Search for tracks across all indexed locations.
        
        Args:
            query (str): Search query
            limit (int): Maximum number of results
            
        Returns:
            list: Media files matching the query
        """
        return self.media_handler.search_tracks(query, limit=limit)
    
    def refresh_library(self):
        """Force a refresh of the media library index.
        
        Returns:
            int: Number of tracks indexed
        """
        count = self.media_handler.update_media_index(force=True)
        
        # Refresh the playlist with any new tracks
        all_tracks = self.media_handler.get_all_indexed_tracks()
        for track in all_tracks:
            if track not in self.playlist:
                self.playlist.append(track)
        
        # Notify plugins
        self.event_bus.publish('on_playlist_loaded', {'playlist': self.playlist})
        
        return count