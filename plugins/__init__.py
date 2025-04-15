# plugins/__init__.py
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union, TypedDict, Literal, TypeVar, Generic
import json
from pydantic import BaseModel, Field

class PlaybackInfo(TypedDict):
    track_name: str
    artist: Optional[str]
    album: Optional[str]
    position: float  # seconds
    duration: float  # seconds

T = TypeVar('T')

class BasePlugin(ABC, Generic[T]):
    """
    Base class for all plugins.
    Plugin developers must inherit from this class and implement
    required methods while optional methods can be overridden as needed.
    """
    
    def __init__(self, player):
        """Initialize with a reference to the main player"""
        self.player = player
        self.name = "Base Plugin"
        self.command_name = None
        self.plugin_id = self.__module__.split('.')[-1]
        self.initialized = True
        self.current_track = None
        self.track_start_time = 0
        # self.is_paused = False
        self.current_temp_file = None  # For tracking temporary audio files
        self.paused_position = 0  # Track position when paused
    
    def is_available(self):
        """Check if the plugin is available for use"""
        return self.initialized
    
    # Common state management
    def set_as_active(self):
        """Set this plugin as the active source"""
        return self.player.plugin_manager.set_active_plugin(self.plugin_id)
    
    def update_playback_state(self, state_dict):
        """Update playback state in the plugin manager"""
        self.player.plugin_manager.update_playback_info(state_dict)
    
    def handle_state_transition(self, action_func, args=None, wait_time=0.5, state_update=None):
        """
        Handle common pattern of action + state update for any plugin type
        
        Parameters:
        -----------
        action_func : function
            The function to execute (play, pause, etc.)
        args : list, optional
            Arguments to pass to the action function
        wait_time : float, optional
            Time to wait after action for state to settle (useful for API calls)
        state_update : dict, optional
            Explicit state updates to apply after the action
        
        Returns:
        --------
        Result of the action function or None if an error occurred
        """
        try:
            # Set this plugin as active
            self.set_as_active()
            
            # Execute the action
            result = action_func(*args) if args else action_func()
            
            # Give API time to update if needed
            if wait_time > 0:
                time.sleep(wait_time)
            
            # Update playback info
            if state_update:
                self.update_playback_state(state_update)
            else:
                self.update_playback_info()
                
            return result
        except Exception as e:
            print(f"Error executing {action_func.__name__ if hasattr(action_func, '__name__') else 'action'}: {e}")
            return None
    
    # Standard media player controls - to be implemented by subclasses
    def play(self, args):
        """
        Standard play command implementation.
        This should be overridden by subclasses to implement specific play logic.
        """
        try:
            if not self._can_play():
                print(f"Cannot play: {self.name} plugin not ready")
                return False
            
            # Call the plugin-specific implementation and handle state transition
            return self.handle_state_transition(
                lambda: self._play_impl(args),
                wait_time=0.5,
                state_update={'state': 'PLAYING'}
            )
        except Exception as e:
            print(f"Error going to play: {e}")
            return False
    
    def pause(self, args):
        """
        Standard pause command implementation.
        """
        try:
            if not self._is_playing():
                print("Nothing is currently playing")
                return False
            
            # Call the plugin-specific implementation and handle state transition
            return self.handle_state_transition(
                lambda: self._pause_impl(args),
                wait_time=0.5,
                state_update={'state': 'PAUSED'}
            )
        except Exception as e:
            print(f"Error going to pause: {e}")
            return False
    
    def stop(self, args):
        """
        Standard stop command implementation.
        """
        try:
            if not self._is_active():
                return True
            
            # Call the plugin-specific implementation and handle state transition
            return self.handle_state_transition(
                lambda: self._stop_impl(args),
                wait_time=0.5,
                state_update={'state': 'STOPPED'}
            )
        except Exception as e:
            print(f"Error going to stop: {e}")
            return False
    
    def next(self, args):
        """
        Standard next track command implementation.
        """
        try:
            if not self._is_active():
                print(f"{self.name} not active")
                return False
            
            # Call the plugin-specific implementation and handle state transition
            return self.handle_state_transition(
                lambda: self._next_impl(args),
                wait_time=0.5
                # No state update - let update_playback_info handle it
            )
        except Exception as e:
                print(f"Error going to next: {e}")
                return False
    
    def prev(self, args):
        """
        Standard previous track command implementation.
        """
        try:
            if not self._is_active():
                print(f"{self.name} not active")
                return False
            
            # Call the plugin-specific implementation and handle state transition
            return self.handle_state_transition(
                lambda: self._prev_impl(args),
                wait_time=0.5
                # No state update - let update_playback_info handle it
            )
        except Exception as e:
            print(f"Error going to previous: {e}")
            return False
    
    # Add to BasePlugin class in __init__.py
    def volume(self, args):
        """
        Standard volume control implementation.
        """
        try:
            if not args or not args[0].isdigit():
                print(f"Usage: {self.command_name} volume <0-100>")
                return False
                
            volume = int(args[0])
            if 0 <= volume <= 100:
                # Call the plugin-specific implementation and handle state transition
                return self.handle_state_transition(
                    lambda: self._set_volume_impl(volume),
                    wait_time=0.5,
                    state_update={'volume': volume}
                )
            else:
                print("Volume must be between 0 and 100")
                return False
        except Exception as e:
            print(f"Error setting volume: {e}")
            return False

    @abstractmethod
    def _set_volume_impl(self, volume):
        """Subclass-specific volume implementation"""
        return False
        
    @abstractmethod
    def _play_impl(self, args):
        """Subclass-specific play implementation"""
        return False
    
    @abstractmethod
    def _pause_impl(self, args):
        """Subclass-specific pause implementation"""
        return False
        
    def _stop_impl(self, args):
        """Subclass-specific stop implementation"""
        return False
        
    def _next_impl(self, args):
        """Subclass-specific next implementation"""
        return False
        
    def _prev_impl(self, args):
        """Subclass-specific previous implementation"""
        return False
    
    def _can_play(self):
        """Check if the plugin can play media"""
        return self.is_available()
    
    def _is_playing(self):
        """Check if this plugin is currently playing"""
        return self._is_active() and self.player.plugin_manager.get_playback_info()['state'] == 'PLAYING'
    
    def _is_active(self):
        """Check if this plugin is the active plugin"""
        return self.player.plugin_manager.get_active_plugin() == self.plugin_id
    
    # Standard methods for playback state
    @abstractmethod
    def update_playback_info(self) -> None:
        """Update the plugin manager with current playback info"""
        # This should be implemented by subclasses that have 
        # service-specific ways to get playback info
        pass
    
    @abstractmethod
    def play_track(self, track_data):
        """
        Play a track selected from search results or listing.
        This should be implemented by subclasses for their specific data format.
        """
        pass
    
    @abstractmethod
    def get_current_playback(self) -> Optional[PlaybackInfo]:
        """
        Get information about current playback.
        Should be implemented by subclasses.
        """
        return None
    
    # Event handlers (can be overridden)
    def on_play(self, data):
        """Called when a track starts playing"""
        pass
    
    def on_pause(self, data):
        """Called when playback is paused"""
        pass
    
    def on_stop(self, data):
        """Called when playback is stopped"""
        pass
    
    def on_playlist_loaded(self, data):
        """Called when a playlist is loaded"""
        pass
    
    def on_volume_change(self, data):
        """Called when volume is changed"""
        pass
    
    def on_now(self, data):
        """Called when the current track is requested"""
        pass
    
    def on_shutdown(self, data):
        """Called when the player is shutting down"""
        self.stop([])
    
    def command_help(self):
        """Return help text for plugin commands"""
        return "No commands available"
    
    def update_playback_state_from_info(self, playback_info):
        """
        Update the plugin manager with standardized playback info
        Handles missing attributes gracefully
        
        Expected plugin-standardized format:
        {
            'track_name': str,
            'artist': str or None,
            'album': str or None,
            'position': float (seconds),
            'duration': float (seconds),
        }
        """
        if playback_info:
            # Define default values for all expected fields
            standardized_info = {
                'track_name': playback_info.get('track_name', 'Unknown'),
                'artist': playback_info.get('artist', None),
                'album': playback_info.get('album', None),
                'position': playback_info.get('position', 0),
                'duration': playback_info.get('duration', 0),
            }
            
            # Update the plugin manager with our standardized info
            self.player.plugin_manager.update_playback_info(standardized_info)

    def play_audio_file(self, file_path, start_pos=0.0, loops=0):
        """
        Helper method to play an audio file using the media handler.
        Useful for plugins that need to play local audio files.
        
        Args:
            file_path (str): Path to the audio file
            start_pos (float): Start position in seconds
            loops (int): Number of times to repeat (-1 for infinite)
            
        Returns:
            tuple: (success, temp_file)
        """
        # Set this plugin as active before playing
        self.set_as_active()
        
        # Use media handler to play the file
        success, temp_file = self.player.media_handler.play_audio(file_path, start_pos, loops)
        
        # Store temp file for later cleanup
        if success and temp_file:
            self.current_temp_file = temp_file
            
        # Store start time for position tracking
        if success:
            self.track_start_time = time.time() - start_pos
            # self.is_paused = False
            
        return success, temp_file

    def pause_audio(self):
        """
        Helper method to pause audio playback.
        
        Returns:
            bool: True if successful
        """
        result = self.player.media_handler.pause_audio()
        if result:
            # self.is_paused = True
            self.paused_position = self.get_audio_position()
        return result

    def resume_audio(self):
        """
        Helper method to resume paused audio playback.
        
        Returns:
            bool: True if successful
        """
        result = self.player.media_handler.resume_audio()
        if result and self.is_paused:
            # self.is_paused = False
            # Adjust start time to maintain correct position tracking
            current_time = time.time()
            self.track_start_time = current_time - self.paused_position
        return result

    def stop_audio(self):
        """
        Helper method to stop audio playback and clean up.
        
        Returns:
            bool: True if successful
        """
        result = self.player.media_handler.stop_audio()
        # self.cleanup_temp_file()
        # self.is_paused = False
        return result

    def set_audio_volume(self, volume):
        """
        Helper method to set audio volume (0.0 to 1.0).
        
        Args:
            volume (float): Volume level between 0.0 and 1.0
            
        Returns:
            bool: True if successful
        """
        return self.player.media_handler.set_audio_volume(volume)

    def is_audio_playing(self):
        """
        Helper method to check if audio is currently playing.
        
        Returns:
            bool: True if audio is playing
        """
        return self.player.media_handler.is_audio_playing()

    def get_audio_position(self):
        """
        Helper method to get current playback position in seconds.
        
        Returns:
            float: Current position in seconds
        """
        # if self.is_paused:
        #     return self.paused_position
            
        # Get position from pygame via media handler
        pos_ms = self.player.media_handler.get_audio_position()
        if pos_ms > 0:
            return pos_ms / 1000.0  # Convert from ms to seconds
            
        # Fallback to time-based tracking
        if self.track_start_time > 0:
            return time.time() - self.track_start_time
            
        return 0.0

    def cleanup_temp_file(self):
        """
        Helper method to clean up temporary file if it exists.
        
        Returns:
            bool: True if successful or no file to clean
        """
        if self.current_temp_file and os.path.exists(self.current_temp_file):
            result = self.player.media_handler.cleanup_audio_file(self.current_temp_file)
            if result:
                self.current_temp_file = None
            return result
        return True

    def _set_volume_impl(self, volume):
        """Default implementation for volume control."""
        return self.set_audio_volume(volume / 100.0) 