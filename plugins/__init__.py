# plugins/__init__.py
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union, TypedDict, Literal, TypeVar, Generic
import json
from pydantic import BaseModel, Field
import os

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

    @staticmethod
    def sub_list_function_call(value=None):
        """
        Decorator that adds a 'list' attribute and an optional value attribute.
        Can be used as @list_attribute or @list_attribute("value").
        """
        def decorator(func):
            # Set the primary 'list' attribute
            func.list = True
            
            # Add the value attribute if provided
            if value is not None:
                func.value = value
            
            return func
        
        # Handle both @list_attribute and @list_attribute("value")
        if callable(value):
            # Called as @list_attribute without parentheses
            func = value
            func.list = True
            return func
        else:
            # Called as @list_attribute("value") with a string argument
            return decorator
    
    def __init__(self, player):
        """Initialize with a reference to the main player"""
        self.player = player
        self.name = "Base Plugin"
        self.command_name = None
        self.plugin_id = self.__module__.split('.')[-1]
        self.initialized = True
        self.current_track = None
        self.track_start_time = 0
        self.current_state = 'STOPPED'  # Track the plugin's internal state
        self.current_temp_file = None  # For tracking temporary audio files
        self.paused_position = 0  # Track position when paused
        
        # Subscribe to standard events if event bus exists
        if hasattr(player, 'event_bus'):
            # Standard player events only
            for event_type, handler_name in [
                (player.STATE_CHANGED, 'on_state_changed'),
                (player.TRACK_CHANGED, 'on_track_changed'),
                (player.SOURCE_CHANGED, 'on_source_changed'),
                (player.POSITION_CHANGED, 'on_position_changed'),
                (player.VOLUME_CHANGED, 'on_volume_changed')
            ]:
                if hasattr(self, handler_name):
                    player.event_bus.subscribe(event_type, getattr(self, handler_name))
    
    def is_available(self):
        """Check if the plugin is available for use"""
        return self.initialized
    
    # Common state management
    def set_as_active(self):
        """Set this plugin as the active source and ensure exclusive playback"""
        if self.player.plugin_manager.get_active_plugin() != self.plugin_id:
            # Request exclusive playback first
            result = self.player.plugin_manager.ensure_exclusive_playback(self.plugin_id)
            if not result:
                print(f"Failed to get exclusive playback for {self.plugin_id}")
                return False
            return True
        return True
    
    def update_playback_state(self, state_dict):
        """Update playback state in the plugin manager"""
        # Track state change internally
        if 'state' in state_dict:
            self.current_state = state_dict['state']
            
        # Update the player's playback info
        self.player.plugin_manager.update_playback_info(state_dict)
    
    def handle_state_transition(self, action_func, args=None, wait_time=0.5, state_update=None):
        """
        Handle common pattern of action + state update for any plugin type
        """
        try:
            # Ensure this plugin has exclusive playback
            if not self.set_as_active():
                print(f"Cannot transition state: failed to set {self.plugin_id} as active source")
                return False
            
            # Reset playback info time to ensure fresh data
            if hasattr(self.player.plugin_manager, 'reset_playback_info_time'):
                self.player.plugin_manager.reset_playback_info_time()
            
            # Execute the action
            result = action_func(*args) if args else action_func()
            
            # Give API time to update if needed
            if wait_time > 0:
                time.sleep(wait_time)
            
            # Update playback info
            if state_update:
                # Track state change internally
                if 'state' in state_update:
                    old_state = self.current_state
                    self.current_state = state_update['state']
                    
                    # Store track start time if transitioning to PLAYING
                    if self.current_state == 'PLAYING' and old_state != 'PLAYING':
                        self.track_start_time = time.time() - self.paused_position
                    
                    # Store paused position if transitioning to PAUSED
                    if self.current_state == 'PAUSED' and old_state == 'PLAYING':
                        self.paused_position = self.get_audio_position()
                    
                    # Reset position if transitioning to STOPPED
                    if self.current_state == 'STOPPED':
                        self.paused_position = 0
                        self.track_start_time = 0
                
                self.update_playback_state(state_update)
            else:
                self.update_playback_info()
                
            return result
        except Exception as e:
            print(f"Error executing {action_func.__name__ if hasattr(action_func, '__name__') else 'action'}: {e}")
            return None
    
    def play(self, args):
        """Overarching play command used by cli to call actions to plugins"""
        try:
            if not self._can_play():
                print(f"Cannot play: {self.name} plugin not ready")
                return False
            
            # Ensure this plugin is the active source
            if not self.set_as_active():
                print(f"Failed to set {self.name} as active source")
                return False
                
            # Call the plugin-specific implementation
            # return self._play_impl(args)
            return self.handle_state_transition(
                lambda: self._play_impl(args),
                wait_time=0.5,
                state_update={'state': 'PLAYING'}
            )
        except Exception as e:
            print(f"Error in play: {e}")
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
                    state_update={'volume': volume / 100.0}  # Normalize to 0-1
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
        if not self._is_active():
            return False
            
        # Use plugin manager's playback info for consistent state
        playback_info = self.player.plugin_manager.get_playback_info()
        return playback_info['state'] == 'PLAYING'
    
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
    
    # Standard event handlers - centralized in the base class
    def on_state_changed(self, data):
        """Called when player state changes"""
        # Only handle if we're the active source
        if self._is_active():
            # Update our internal state
            self.current_state = data['new_state']
            # Call plugin-specific hook
            self.on_state_changed_hook(data)
    
    def on_track_changed(self, data):
        """Called when track changes"""
        # Only handle if we're the active source
        if self._is_active():
            # Update our internal tracking
            self.current_track = data.get('track_name')
            # Reset tracking variables
            if self.current_state == 'PLAYING':
                self.track_start_time = time.time()
                self.paused_position = 0
            # Call plugin-specific hook
            self.on_track_changed_hook(data)
    
    def on_source_changed(self, data):
        """Called when audio source changes"""
        previous_source = data.get('previous_source')
        new_source = data.get('new_source')
        
        # If we're losing active status, stop any playback
        if previous_source == self.plugin_id and new_source != self.plugin_id:
            self.stop_audio()
            # Call plugin-specific hook
            self.on_source_changed_hook(data)
    
    def on_position_changed(self, data):
        """Called when playback position changes"""
        # Only handle if we're the active source
        if self._is_active():
            position = data.get('position', 0)
            # If position jumped significantly, adjust our tracking
            if abs(position - self.get_audio_position()) > 1.0:
                if self.current_state == 'PLAYING':
                    self.track_start_time = time.time() - position
                elif self.current_state == 'PAUSED':
                    self.paused_position = position
            # Call plugin-specific hook
            self.on_position_changed_hook(data)
    
    def on_volume_changed(self, data):
        """Called when volume changes"""
        # Only handle if we're the active source
        if self._is_active():
            new_volume = data.get('new_volume', 0)
            self._set_volume_impl(int(new_volume * 100))
            # Call plugin-specific hook
            self.on_volume_changed_hook(data)

    
    # Hook methods that plugins can override without reimplementing event handlers
    def on_state_changed_hook(self, data):
        """Override this to handle state changes"""
        pass
    
    def on_track_changed_hook(self, data):
        """Override this to handle track changes"""
        pass
    
    def on_source_changed_hook(self, data):
        """Override this to handle source changes"""
        pass
    
    def on_position_changed_hook(self, data):
        """Override this to handle position changes"""
        pass
    
    def on_volume_changed_hook(self, data):
        """Override this to handle volume changes"""
        pass
    
    def command_help(self):
        """Return help text for plugin commands"""
        return """
Available commands:
  play        - Start/resume playback
  pause       - Pause playback
  stop        - Stop playback
  next        - Skip to next track
  prev        - Go to previous track
  volume <0-100> - Set volume level
"""
    
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
                'genre': playback_info.get('genre', None),
                'year': playback_info.get('year', None),
                'state': playback_info.get('state', self.current_state)
            }
            
            # Track state change internally
            if 'state' in playback_info:
                self.current_state = playback_info['state']
            
            # Update the plugin manager with our standardized info
            self.player.plugin_manager.update_playback_info(standardized_info)

    def play_audio_file(self, file_path, loops=0):
        """
        Helper method to play an audio file using the media handler.
        """
        # Ensure exclusive playback for this plugin
        if not self.set_as_active():
            print(f"Failed to get exclusive playback for {self.plugin_id}")
            return False, None
            
        start_pos = self.paused_position if self.paused_position and self.paused_position > 0 else 0.0
        
        # Use media handler to play the file
        success, temp_file = self.player.media_handler.play_audio(file_path, start_pos, loops)
        
        # Store start time for position tracking
        if success:
            self.track_start_time = time.time() - start_pos
            self.current_state = 'PLAYING'
            
            # Update playback info
            self.player.plugin_manager.update_playback_info({
                'state': 'PLAYING'
            })
            
        return success, temp_file

    def pause_audio(self):
        """
        Helper method to pause audio playback.
        
        Returns:
            bool: True if successful
        """
        result = self.player.media_handler.pause_audio()
        if result:
            self.current_state = 'PAUSED'
            self.paused_position = self.get_audio_position()
            
            # Update playback info
            self.player.plugin_manager.update_playback_info({
                'state': 'PAUSED'
            })
            
        return result

    def resume_audio(self):
        """
        Helper method to resume paused audio playback.
        
        Returns:
            bool: True if successful
        """
        result = self.player.media_handler.resume_audio()
        if result:
            self.current_state = 'PLAYING'
            
            # Adjust start time to maintain correct position tracking
            current_time = time.time()
            self.track_start_time = current_time - self.paused_position
            
            # Update playback info
            self.player.plugin_manager.update_playback_info({
                'state': 'PLAYING'
            })
            
        return result

    def stop_audio(self):
        """
        Helper method to stop audio playback and clean up.
        
        Returns:
            bool: True if successful
        """
        result = self.player.media_handler.stop_audio()
        self.cleanup_temp_file()
        self.current_state = 'STOPPED'
        self.paused_position = 0
        self.track_start_time = 0
        
        # Update playback info
        self.player.plugin_manager.update_playback_info({
            'state': 'STOPPED'
        })
        
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
        if self.current_state == 'PAUSED':
            return self.paused_position
            
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
    
    def download(self, url, file_name, download_dir):
        """Wrapper for media_handler function to pass to plugins"""
        file_path = self.player.media_handler.download_media_file(url, file_name, download_dir)
        return file_path