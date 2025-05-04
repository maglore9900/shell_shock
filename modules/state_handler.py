from abc import ABC, abstractmethod
import os
import time

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
        if player.playlist and player.current_index < len(player.playlist):
            player.current_track = player.playlist[player.current_index]
            
            # Get track duration before playing
            player.current_track_length = player.media_handler.get_track_duration(player.current_track)
            
            # Use MediaHandler method to play
            success, temp_file = player.media_handler.play_audio(player.current_track)
            if not success:
                print(f"Cannot play {os.path.basename(player.current_track)}: format not supported")
                return
            
            player.track_start_time = time.time()
            
            # Update playback info
            player.update_playback_info({
                'state': 'PLAYING',
                'track_name': os.path.basename(player.current_track),
                'source': 'local'
            })
            
            # Switch to playing state - happens in update_playback_info
            
            # Make sure plugin manager knows local is the active source
            player.plugin_manager.set_active_plugin('local')
            
            # Update play stats
            player.media_handler.update_play_stats(player.current_track)
            
        else:
            print("No tracks in playlist")
    
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
    
    def previous_track(self, player):
        """Go to previous track but remain stopped"""
        if player.playlist:
            player.navigate_track("prev")
    
    def get_state_name(self):
        return "STOPPED"


class PlayingState(PlayerStateInterface):
    """Represents the player in playing state"""
    
    def play(self, player):
        """Already playing, do nothing"""
        pass
    
    def pause(self, player):
        """Pause the current playback"""
        player.media_handler.pause_audio()
        
        # Update playback info
        player.update_playback_info({'state': 'PAUSED'})
    
    def stop(self, player):
        """Stop the current playback"""
        player.media_handler.stop_audio()
        
        # Update playback info
        player.update_playback_info({'state': 'STOPPED'})
    
    def next_track(self, player):
        """Play the next track"""
        if player.playlist:
            player.stop()
            player.navigate_track("next")
            player.play()
    
    def previous_track(self, player):
        """Play the previous track"""
        if player.playlist:
            player.stop()
            player.navigate_track("prev")
            player.play()
    
    def get_state_name(self):
        return "PLAYING"


class PausedState(PlayerStateInterface):
    """Represents the player in paused state"""
    
    def play(self, player):
        """Resume playback"""
        player.media_handler.resume_audio()
        
        # Update playback info
        player.update_playback_info({'state': 'PLAYING'})
    
    def pause(self, player):
        """Already paused, do nothing"""
        pass
    
    def stop(self, player):
        """Stop the paused playback"""
        player.media_handler.stop_audio()
        
        # Update playback info
        player.update_playback_info({'state': 'STOPPED'})
    
    def next_track(self, player):
        """Play the next track"""
        if player.playlist:
            player.stop()
            player.navigate_track("next")
            player.play()
    
    def previous_track(self, player):
        """Play the previous track"""
        if player.playlist:
            player.stop()
            player.navigate_track("prev")
            player.play()
    
    def get_state_name(self):
        return "PAUSED"