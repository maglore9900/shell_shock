from abc import ABC, abstractmethod
import os
import time
from modules.logging_utils import log_function_call, app_logger as log

class PlayerStateInterface(ABC):
    """Interface for player states"""
    
    @abstractmethod
    def play(self, player):
        """Handle play command in this state"""
        pass
    
    @abstractmethod
    def pause(self, player):
        """Handle pause command in this state"""
        pass
    
    @abstractmethod
    def stop(self, player):
        """Handle stop command in this state"""
        pass
    
    @abstractmethod
    def next_track(self, player):
        """Handle next track command in this state"""
        pass
    
    @abstractmethod
    def previous_track(self, player):
        """Handle previous track command in this state"""
        pass
    
    @abstractmethod
    def get_state_name(self):
        """Return the string representation of this state"""
        pass
    


class StoppedState(PlayerStateInterface):
    """Represents the player in stopped state"""
    
    def play(self, player):
        """Start playback from stopped state"""
        if not player.playlist or player.current_index >= len(player.playlist):
            log.warning("No tracks in playlist")
            print("No tracks in playlist")
            return
            
        try:
            # Get the current track
            player.current_track = player.playlist[player.current_index]
            
            # Load track info - this will use the cache if available
            try:
                player.current_track_info = player.media_handler.get_track_info(player.current_track)
                player.current_track_length = player.current_track_info.duration or 0
            except Exception as e:
                log.error(f"Error loading track info: {e}")
                # Fallback to basic info
                player.current_track_length = player.media_handler.get_track_duration(player.current_track)
                player.current_track_info = None
            
            # Play the track
            success, temp_file = player.media_handler.play_audio(player.current_track)
            if not success:
                log.error(f"Cannot play {os.path.basename(player.current_track)}: format not supported")
                print(f"Cannot play {os.path.basename(player.current_track)}: format not supported")
                return
            
            player.track_start_time = time.time()
            
            # Make sure plugin manager knows local is the active source
            player.plugin_manager.set_active_plugin('local')
            
            # Update play stats
            player.media_handler.update_play_stats(player.current_track)
            
            # Prepare playback info
            playback_info = {
                'state': 'PLAYING',
                'source': 'local'
            }
            
            # Add track info if available
            if player.current_track_info:
                playback_info.update(player.current_track_info.to_dict())
            else:
                # Basic fallback info
                playback_info['track_name'] = os.path.basename(player.current_track)
            
            # Update playback info - this handles state change and events
            player.update_playback_info(playback_info)
            
        except Exception as e:
            log.error(f"Error in play(): {e}")
            print(f"Error starting playback: {e}")
    
    def pause(self, player):
        """Cannot pause when stopped"""
        print("Cannot pause: player is stopped")
    
    def stop(self, player):
        """Already stopped, do nothing"""
        pass
    
    def next_track(self, player):
        """Go to next track but remain stopped"""
        if player.playlist:
            player.navigate_track("next")
            # Update current_track but don't start playback
            player.current_track = player.playlist[player.current_index]
            
            # Load track info in background
            try:
                player.current_track_info = player.media_handler.get_track_info(player.current_track)
            except Exception as e:
                log.error(f"Error loading track info for next track: {e}")
                player.current_track_info = None
    
    def previous_track(self, player):
        """Go to previous track but remain stopped"""
        if player.playlist:
            player.navigate_track("prev")
            # Update current_track but don't start playback
            player.current_track = player.playlist[player.current_index]
            
            # Load track info in background
            try:
                player.current_track_info = player.media_handler.get_track_info(player.current_track)
            except Exception as e:
                log.error(f"Error loading track info for previous track: {e}")
                player.current_track_info = None
    
    def get_state_name(self):
        return "STOPPED"


class PlayingState(PlayerStateInterface):
    """Represents the player in playing state"""
    
    def play(self, player):
        """Already playing, do nothing"""
        pass
    
    def pause(self, player):
        """Pause the current playback"""
        try:
            player.media_handler.pause_audio()
            
            # Store pause time for accurate position tracking
            player.pause_time = time.time()
            
            # Update playback info - this handles state change and events
            player.update_playback_info({'state': 'PAUSED'})
        except Exception as e:
            log.error(f"Error in pause(): {e}")
            print(f"Error pausing playback: {e}")
    
    def stop(self, player):
        """Stop the current playback"""
        try:
            player.media_handler.stop_audio()
            
            # Update playback info - this handles state change and events
            player.update_playback_info({'state': 'STOPPED'})
        except Exception as e:
            log.error(f"Error in stop(): {e}")
            print(f"Error stopping playback: {e}")
    
    def next_track(self, player):
        """Play the next track"""
        if player.playlist:
            try:
                # First stop current playback
                player.media_handler.stop_audio()
                
                # Navigate to next track
                player.navigate_track("next")
                
                # Update current track
                player.current_track = player.playlist[player.current_index]
                
                # Load track info - this will use the cache if available
                try:
                    player.current_track_info = player.media_handler.get_track_info(player.current_track)
                    player.current_track_length = player.current_track_info.duration or 0
                except Exception as e:
                    log.error(f"Error loading track info: {e}")
                    # Fallback to basic info
                    player.current_track_length = player.media_handler.get_track_duration(player.current_track)
                    player.current_track_info = None
                
                # Play the track
                success, temp_file = player.media_handler.play_audio(player.current_track)
                if not success:
                    log.error(f"Cannot play {os.path.basename(player.current_track)}: format not supported")
                    print(f"Cannot play {os.path.basename(player.current_track)}: format not supported")
                    # Update to stopped state
                    player.update_playback_info({'state': 'STOPPED'})
                    return
                
                player.track_start_time = time.time()
                
                # Update play stats
                player.media_handler.update_play_stats(player.current_track)
                
                # Prepare playback info
                playback_info = {
                    'state': 'PLAYING',
                    'source': 'local'
                }
                
                # Add track info if available
                if player.current_track_info:
                    playback_info.update(player.current_track_info.to_dict())
                else:
                    # Basic fallback info
                    playback_info['track_name'] = os.path.basename(player.current_track)
                
                # Update playback info - this handles state change and events
                player.update_playback_info(playback_info)
                
            except Exception as e:
                log.error(f"Error in next_track(): {e}")
                print(f"Error playing next track: {e}")
    
    def previous_track(self, player):
        """Play the previous track"""
        if player.playlist:
            try:
                # First stop current playback
                player.media_handler.stop_audio()
                
                # Navigate to previous track
                player.navigate_track("prev")
                
                # Update current track
                player.current_track = player.playlist[player.current_index]
                
                # Load track info - this will use the cache if available
                try:
                    player.current_track_info = player.media_handler.get_track_info(player.current_track)
                    player.current_track_length = player.current_track_info.duration or 0
                except Exception as e:
                    log.error(f"Error loading track info: {e}")
                    # Fallback to basic info
                    player.current_track_length = player.media_handler.get_track_duration(player.current_track)
                    player.current_track_info = None
                
                # Play the track
                success, temp_file = player.media_handler.play_audio(player.current_track)
                if not success:
                    log.error(f"Cannot play {os.path.basename(player.current_track)}: format not supported")
                    print(f"Cannot play {os.path.basename(player.current_track)}: format not supported")
                    # Update to stopped state
                    player.update_playback_info({'state': 'STOPPED'})
                    return
                
                player.track_start_time = time.time()
                
                # Update play stats
                player.media_handler.update_play_stats(player.current_track)
                
                # Prepare playback info
                playback_info = {
                    'state': 'PLAYING',
                    'source': 'local'
                }
                
                # Add track info if available
                if player.current_track_info:
                    playback_info.update(player.current_track_info.to_dict())
                else:
                    # Basic fallback info
                    playback_info['track_name'] = os.path.basename(player.current_track)
                
                # Update playback info - this handles state change and events
                player.update_playback_info(playback_info)
                
            except Exception as e:
                log.error(f"Error in previous_track(): {e}")
                print(f"Error playing previous track: {e}")
    
    def get_state_name(self):
        return "PLAYING"

class PausedState(PlayerStateInterface):
    """Represents the player in paused state"""
    
    def play(self, player):
        """Resume playback"""
        try:
            player.media_handler.resume_audio()
            
            # Account for paused time in track_start_time
            if hasattr(player, 'pause_time'):
                pause_duration = time.time() - player.pause_time
                player.track_start_time += pause_duration
            
            # Update playback info - this handles state change and events
            player.update_playback_info({'state': 'PLAYING'})
        except Exception as e:
            log.error(f"Error in play() (resume): {e}")
            print(f"Error resuming playback: {e}")
    
    def pause(self, player):
        """Already paused, do nothing"""
        pass
    
    def stop(self, player):
        """Stop the paused playback"""
        try:
            player.media_handler.stop_audio()
            
            # Update playback info - this handles state change and events
            player.update_playback_info({'state': 'STOPPED'})
        except Exception as e:
            log.error(f"Error in stop(): {e}")
            print(f"Error stopping playback: {e}")
    
    def next_track(self, player):
        """Play the next track"""
        if player.playlist:
            try:
                # First stop current playback
                player.media_handler.stop_audio()
                
                # Navigate to next track
                player.navigate_track("next")
                
                # Update current track
                player.current_track = player.playlist[player.current_index]
                
                # Load track info - this will use the cache if available
                try:
                    player.current_track_info = player.media_handler.get_track_info(player.current_track)
                    player.current_track_length = player.current_track_info.duration or 0
                except Exception as e:
                    log.error(f"Error loading track info: {e}")
                    # Fallback to basic info
                    player.current_track_length = player.media_handler.get_track_duration(player.current_track)
                    player.current_track_info = None
                
                # Play the track
                success, temp_file = player.media_handler.play_audio(player.current_track)
                if not success:
                    log.error(f"Cannot play {os.path.basename(player.current_track)}: format not supported")
                    print(f"Cannot play {os.path.basename(player.current_track)}: format not supported")
                    # Update to stopped state
                    player.update_playback_info({'state': 'STOPPED'})
                    return
                
                player.track_start_time = time.time()
                
                # Update play stats
                player.media_handler.update_play_stats(player.current_track)
                
                # Prepare playback info
                playback_info = {
                    'state': 'PLAYING',
                    'source': 'local'
                }
                
                # Add track info if available
                if player.current_track_info:
                    playback_info.update(player.current_track_info.to_dict())
                else:
                    # Basic fallback info
                    playback_info['track_name'] = os.path.basename(player.current_track)
                
                # Update playback info - this handles state change and events
                player.update_playback_info(playback_info)
                
            except Exception as e:
                log.error(f"Error in next_track(): {e}")
                print(f"Error playing next track: {e}")
    
    def previous_track(self, player):
        """Play the previous track"""
        if player.playlist:
            try:
                # First stop current playback
                player.media_handler.stop_audio()
                
                # Navigate to previous track
                player.navigate_track("prev")
                
                # Update current track
                player.current_track = player.playlist[player.current_index]
                
                # Load track info - this will use the cache if available
                try:
                    player.current_track_info = player.media_handler.get_track_info(player.current_track)
                    player.current_track_length = player.current_track_info.duration or 0
                except Exception as e:
                    log.error(f"Error loading track info: {e}")
                    # Fallback to basic info
                    player.current_track_length = player.media_handler.get_track_duration(player.current_track)
                    player.current_track_info = None
                
                # Play the track
                success, temp_file = player.media_handler.play_audio(player.current_track)
                if not success:
                    log.error(f"Cannot play {os.path.basename(player.current_track)}: format not supported")
                    print(f"Cannot play {os.path.basename(player.current_track)}: format not supported")
                    # Update to stopped state
                    player.update_playback_info({'state': 'STOPPED'})
                    return
                
                player.track_start_time = time.time()
                
                # Update play stats
                player.media_handler.update_play_stats(player.current_track)
                
                # Prepare playback info
                playback_info = {
                    'state': 'PLAYING',
                    'source': 'local'
                }
                
                # Add track info if available
                if player.current_track_info:
                    playback_info.update(player.current_track_info.to_dict())
                else:
                    # Basic fallback info
                    playback_info['track_name'] = os.path.basename(player.current_track)
                
                # Update playback info - this handles state change and events
                player.update_playback_info(playback_info)
                
            except Exception as e:
                log.error(f"Error in previous_track(): {e}")
                print(f"Error playing previous track: {e}")
    
    def get_state_name(self):
        return "PAUSED"