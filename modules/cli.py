import threading
import time
import readchar
import os
from modules.player import PlayerState, clear_screen
from modules.logging_utils import log_function_call,  app_logger as log



class MusicPlayerCLI:
    """Command-line interface for the music player"""
    
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
        """Initialize with a player instance"""
        self.player = player
        if hasattr(player, 'event_bus'):
            player.event_bus.subscribe(player.STATE_CHANGED, self.handle_state_changed)
            player.event_bus.subscribe(player.TRACK_CHANGED, self.handle_track_changed)
            player.event_bus.subscribe(player.SOURCE_CHANGED, self.handle_source_changed)
            player.event_bus.subscribe(player.VOLUME_CHANGED, self.handle_volume_changed)
        
        self.paginate_cursor_position = 0
        # Define commands
        self.commands = {
            'load': self.load_directory,
            'play': self.play,
            'pause': self.pause,
            'stop': self.stop,
            'next': self.next_track,
            'prev': self.previous_track,
            'volume': self.set_volume,
            'status': self.show_status,
            'list': self.list_tracks,
            'help': self.show_help,
            'exit': self.exit,
            'playlists': self.show_playlists,
            # 'loadpl': self.load_user_playlist,
            'savepl': self.save_current_as_playlist,
            'shuffle': self.toggle_shuffle,
            'createpl': self.create_playlist,
            'addto': self.add_to_playlist,
            'rmfrom': self.remove_from_playlist,
            'savet': self.save_current_track,
            'now': self.show_now_playing,
            'search': self.search_tracks,
            'settings': self.show_settings_menu,
        }
        
        # Add plugin commands - only for enabled plugins
        self.add_plugin_commands()
    
    # Event handlers for state events
    def handle_state_changed(self, data):
        """Handle state change events for UI updates"""
        # The CLI doesn't need to do anything immediately with state changes
        # This is mostly for future UI enhancements or reactive displays
        pass

    def handle_track_changed(self, data):
        """Handle track change events for UI updates"""
        # Could update display if we add a persistent UI in the future
        pass

    def handle_source_changed(self, data):
        """Handle source change events for UI updates"""
        # Could update prompt or display when source changes
        pass

    def handle_volume_changed(self, data):
        """Handle volume change events for UI updates"""
        # Could show volume indicator if we add a persistent UI
        pass

    def add_plugin_commands(self):
        """Add commands for each plugin and subscribe to plugin events"""
        # Use the plugin manager to get command names
        command_names = self.player.plugin_manager.get_plugin_command_names()
        for plugin_name, command_name in command_names.items():
            plugin = self.player.plugins[plugin_name]['instance']
            
            # Register the command
            self.commands[command_name] = lambda args, plugin=plugin, name=plugin_name: self.plugin_command(plugin, name, args)
            
            # Subscribe to plugin-specific events if needed
            # This can be extended based on specific plugins' needs
    
    # Add a wrapper method for plugin functions that need pagination
    def plugin_paginated_results(self, plugin, command_name, results, play_callback=None, custom_actions=None):
        """
        Handle paginated results from a plugin command.
        
        Args:
            plugin: The plugin instance
            command_name: Name of the command that generated results
            results: List of items to display
            play_callback: Function to call when an item is selected (receives selected item)
            custom_actions: Dictionary of key -> (display_name, function) for special keys
        
        Returns:
            Selected item or None if canceled
        """
        plugin_display_name = plugin.name if hasattr(plugin, 'name') else command_name
        return self.get_paginated_selection(
            items=results,
            title=f"{plugin_display_name} {command_name.title()}",
            play_action=play_callback,
            custom_actions=custom_actions
        )

    def plugin_command(self, plugin, plugin_name, args):
        """Handle a plugin command"""
        if not args:
            # No arguments, show help
            print(f"\n{plugin.name} Plugin")
            if hasattr(plugin, 'command_help'):
                print(plugin.command_help())
            return
        
        # The first argument is the sub-command
        subcmd = args[0].lower()
        subcmd_args = args[1:] if len(args) > 1 else []
        
        # Try to call the matching method on the plugin
        if hasattr(plugin, subcmd):
            try:
                method = getattr(plugin, subcmd)
                result = method(subcmd_args)
                # Check if the result is a list/dict that should be paginated
                # log.info(f"method: {method}")
                if hasattr(plugin, 'paginate_commands') and subcmd in plugin.paginate_commands:
                    # Define play callback based on the command type
                    play_callback = None
                    method = getattr(plugin, subcmd)
                    if hasattr(method, 'list') and hasattr(method, 'value'):
                        target_method = method.value  # Store the target method name (e.g., "list")
                        # Create a more comprehensive callback function
                        def complete_callback(item):
                            # First call the target method to get results
                            result = getattr(plugin, target_method)(item)
                            if result and isinstance(result, (list, dict)):
                                # Now call the pagination function on the result
                                return self.plugin_paginated_results(plugin, target_method, result, 
                                    lambda subitem: plugin.play(subitem))
                            return result
                        play_callback = complete_callback
                    elif hasattr(plugin, 'play'):
                        # log.info("play")
                        # Generic fallback
                        def generic_play(item):
                            if isinstance(item, (tuple, list)) and len(item) > 1:
                                return plugin.play([item[1]])  # Assume second element is ID
                            return False
                        play_callback = generic_play
                    
                    # Display paginated results
                    self.plugin_paginated_results(plugin, subcmd, result, play_callback)
                    return
                
                # Set the plugin as active for playback-related commands
                if subcmd in ['play', 'pause', 'next', 'prev', 'previous']:
                    # Just set the plugin as active and let the player handle state changes
                    self.player.plugin_manager.set_active_plugin(plugin_name)
                    # No need to force state checks - the event system will update UI as needed
                
                return result
            except Exception as e:
                print(f"Error in plugin command: {e}")
        else:
            print(f"Unknown {plugin.name} command: {subcmd}")
            print(f"Type '{plugin.name.lower()}' for available commands")
    
    def load_directory(self, args):
        """Load music from a directory"""
        if not args:
            print("Usage: load <directory_path>")
            return
        
        self.player.load_media(args[0])
    
    def play(self, args):
        """Start or resume playback"""
        # Check if any plugin is currently active
        active_plugin = self.player.plugin_manager.get_active_plugin()
        
        if active_plugin != 'local':
            # Let the active plugin handle playback
            plugin = self.player.plugins.get(active_plugin)
            if plugin and hasattr(plugin, 'play'):
                plugin.play(args)
                return
                
        # Fall back to local playback
        self.player.play()
    
    def pause(self, args):
        """Pause playback"""
        # Use the player's pause method which will handle routing to the right plugin
        self.player.pause()
    
    def stop(self, args):
        """Stop playback"""
        # Use the player's stop method which will handle routing to the right plugin
        self.player.stop()
    
    def next_track(self, args):
        """Play the next track"""
        # Check if any plugin is currently active
        active_plugin = self.player.plugin_manager.get_active_plugin()
        
        if active_plugin != 'local':
            # Let the active plugin handle next track
            plugin = self.player.plugins.get(active_plugin)
            if plugin and hasattr(plugin, 'next'):
                plugin.next(args)
                return
                
        # Fall back to local playback
        self.player.next_track()
    
    def previous_track(self, args):
        """Play the previous track"""
        # Check if any plugin is currently active
        active_plugin = self.player.plugin_manager.get_active_plugin()
        
        if active_plugin != 'local':
            # Let the active plugin handle previous track
            plugin = self.player.plugins.get(active_plugin)
            if plugin and hasattr(plugin, 'prev'):
                plugin.prev(args)
                return
                
        # Fall back to local playback
        self.player.previous_track()
    
    def set_volume(self, args):
        """Set volume"""
        if args and args[0].isdigit():
            volume = int(args[0]) / 100
            self.player.set_volume(volume)
        else:
            print("Usage: volume <0-100>")
    
    def show_status(self, args):
        """Show player status"""
        status = self.player.get_status()
        print("\nPlayer Status:")
        print("-" * 30)
        for key, value in status.items():
            print(f"{key}: {value}")
    
    def list_tracks(self, args):
        """
        List all tracks in a playlist with pagination.
        
        Usage: list [playlist_name]
        If no playlist is specified, shows the currently loaded tracks.
        """
        tracks = None
        playlist_name = None
        
        # Check if a specific playlist was requested
        if args and args[0]:
            playlist_name = args[0]
            # Check if playlist exists
            if playlist_name not in self.player.user_playlists:
                print(f"Playlist not found: {playlist_name}")
                print("Available playlists:")
                for name in self.player.user_playlists:
                    print(f"  {name}")
                return
            
            # Get tracks from the specified playlist
            tracks = self.player.user_playlists[playlist_name]['tracks']
            if not tracks:
                print(f"Playlist '{playlist_name}' is empty")
                return
        else:
            # Use current media/playlist
            tracks = self.player.media
            if not tracks:
                print("Current playlist is empty")
                return
        
        # Define play action callback
        def play_selected_track(track):
            # If from a playlist that's not loaded, load it first
            if playlist_name and playlist_name != self.player.current_playlist_name:
                self.player.load_playlist(playlist_name)
                print(f"Loaded playlist: {playlist_name}")
            
            # Set index and play
            idx = tracks.index(track)
            self.player.current_index = idx
            self.stop(args)
            self.play(args)
            return True
        
        # Use the simplified pagination function
        self.get_paginated_selection(
            items=tracks,
            title=f"{'Playlist: ' + playlist_name if playlist_name else 'Media'} ({len(tracks)} tracks)",
            play_action=play_selected_track
        )
    
    def show_help(self, args):
        """Show available commands"""
        print("\nAvailable commands:")
        print("  load <dir>    - Load music from directory")
        print("  play          - Start/resume playback")
        print("  pause         - Pause playback")
        print("  stop          - Stop playback")
        print("  next          - Play next track")
        print("  prev          - Play previous track")
        print("  volume <0-100> - Set volume")
        print("  status        - Show player status")
        print("  list          - List all tracks")
        print("  search <term> [--strict] - Search for tracks by name")
        print("  settings      - Access settings menu")
        
        # Show plugin commands with correct command names
        if self.player.plugins:
            print("\nPlugin commands:")
            for plugin_name, plugin_info in self.player.plugins.items():
                # Use the command_name from plugin_info
                command_name = plugin_info['command_name']
                plugin_display_name = plugin_info['name']
                print(f"  {command_name}        - {plugin_display_name} commands")
                
        print("\nPlaylist commands:")
        print("  playlists     - Show available playlists")
        # print("  loadpl <name> - Load a specific playlist")
        print("  createpl <name> - Create a new empty playlist")
        print("  savepl <name> - Save current playlist under a name")
        print("  addto <playlist> [track_num|search_term] - Add tracks to playlist")
        print("  rmfrom <playlist> <track_num> - Remove track from playlist")
        print("  savet [playlist] - Save current track to a playlist")
        print("  shuffle       - Toggle shuffle mode on/off")
        
        print("\nMisc commands:")
        print("  now           - Show now playing screen")
        print("  help          - Show this help")
        print("  exit          - Exit the player")
    
    def exit(self, args):
        """Exit the player"""
        # Unsubscribe from events before shutting down
        if hasattr(self.player, 'event_bus'):
            self.player.event_bus.unsubscribe(self.player.STATE_CHANGED, self.handle_state_changed)
            self.player.event_bus.unsubscribe(self.player.TRACK_CHANGED, self.handle_track_changed)
            self.player.event_bus.unsubscribe(self.player.SOURCE_CHANGED, self.handle_source_changed)
            self.player.event_bus.unsubscribe(self.player.VOLUME_CHANGED, self.handle_volume_changed)
        
        self.player.shutdown()
        clear_screen()
        print("Goodbye!")
        import sys
        sys.exit(0)
    
    def show_playlists(self, args):
        """List all available playlists with pagination."""
        if not self.player.user_playlists:
            print("No playlists found")
            return
        
        # Prepare display items with name and track count
        playlist_items = [(name, info) for name, info in self.player.user_playlists.items()]
        
        # Define play action callback (loads and plays the playlist)
        def load_and_play_selected_playlist(item):
            name, _ = item
            self.player.load_playlist(name)
            print(f"Loaded playlist: {name}")
            self.player.current_index = 0  # Start from the first track
            self.player.play()
            return True
        
        # Define custom action to view playlist contents
        def view_playlist_contents():
            selected_item = playlist_items[self.paginate_cursor_position]
            name, _ = selected_item
            self.list_tracks([name])
            # Return None to stay in the playlist selection screen after returning
            return True
        
        # Define custom actions
        custom_actions = {
            'v': ('View playlist contents', view_playlist_contents)
        }
        
        # Custom formatter for playlist items
        def item_formatter(i, item, is_current, is_selected):
            name, info = item
            is_current_playlist = name == self.player.current_playlist_name
            current_marker = " *" if is_current_playlist else ""
            selector = "→ " if is_selected else "  "
            return f"{selector}{i}. {name}{current_marker} ({len(info['tracks'])} tracks)"
        
        # Use the simplified pagination function with a custom formatter
        result = self.paginate_items(
            items=playlist_items,
            header=lambda page, total: print(f"\nAvailable Playlists ({len(playlist_items)}) - Page {page}/{total}:"),
            footer=lambda page, total: print(f"\nPage {page}/{total} - Options:\n  → / ← - Next/Previous page\n  ↑ / ↓ - Move selector\n  Enter - Load selected playlist\n  v - View playlist contents\n  c - Cancel"),
            item_formatter=item_formatter,
            play_callback=load_and_play_selected_playlist,
            custom_actions=custom_actions
        )
        
        # Handle the result if not handled by callbacks
        if result is None:
            return  # User canceled

    def load_user_playlist(self, args):
        """Load a specific playlist."""
        if not args:
            print("Usage: loadpl <name>")
            return
        
        playlist_name = args[0]
        if playlist_name in self.player.user_playlists:
            self.player.load_playlist(playlist_name)
        else:
            print(f"Playlist not found: {playlist_name}")
            print("\nAvailable playlists:")
            for name in self.player.user_playlists:
                print(f"  {name}")

    def save_current_as_playlist(self, args):
        """Save the current playlist as a user playlist."""
        if not args:
            print("Usage: savepl <name>")
            return
        
        if not self.player.playlist:
            print("Current playlist is empty")
            return
        
        playlist_name = args[0]
        if self.player.save_current_as_playlist(playlist_name):
            print(f"Saved current playlist as: {playlist_name}")

    def create_playlist(self, args):
        """Create a new empty playlist."""
        if not args:
            print("Usage: createpl <name>")
            return
        
        playlist_name = args[0]
        
        if playlist_name in self.player.user_playlists:
            print(f"Playlist already exists: {playlist_name}")
            choice = input("Do you want to overwrite it? (y/n): ")
            if choice.lower() != 'y':
                return
        
        # Create an empty playlist
        if self.player.save_playlist(playlist_name, []):
            print(f"Created empty playlist: {playlist_name}")
            print("Use 'addto' command to add tracks")

    def add_to_playlist(self, args):
        """Add tracks to a playlist."""
        if len(args) < 1:
            print("Usage: addto <playlist_name> [track_number|search_term]")
            return
        
        playlist_name = args[0]
        
        # If track_number is provided and is a digit, add that track
        if len(args) > 1 and args[1].isdigit():
            track_num = int(args[1])
            if 1 <= track_num <= len(self.player.playlist):
                track_path = self.player.playlist[track_num - 1]
                if self.player.add_to_playlist(playlist_name, track_path):
                    print(f"Added track {track_num} to playlist: {playlist_name}")
            else:
                print(f"Invalid track number. Must be between 1 and {len(self.player.playlist)}")
        
        # If search terms are provided, search for tracks
        elif len(args) > 1:
            # Get search term from remaining arguments
            search_term = ' '.join(args[1:]).lower()
            self._search_and_add_to_playlist(playlist_name, search_term)
        
        # Otherwise, add the current track
        elif self.player.current_track:
            if self.player.add_to_playlist(playlist_name, self.player.current_track):
                print(f"Added current track to playlist: {playlist_name}")
        else:
            print("No track is currently playing. Use 'addto <playlist> <track_number>' or 'addto <playlist> <search_term>' instead.")

    def _search_and_add_to_playlist(self, playlist_name, search_term):
        """Search for tracks matching a term and add selected ones to a playlist."""
        if not self.player.playlist:
            print("Main playlist is empty. Load some tracks first.")
            return
        
        print(f"Searching for '{search_term}' in {len(self.player.playlist)} tracks...")
        
        # Find matching tracks
        matches = []
        
        for i, track_path in enumerate(self.player.playlist):
            track_name = os.path.basename(track_path).lower()
            
            # Check for match - flexible search
            if search_term in track_name:
                matches.append((i, track_path))
        
        if not matches:
            print(f"No tracks found matching '{search_term}'")
            return
        
        print(f"\nFound {len(matches)} tracks matching '{search_term}':")
        
        # Display results with numbers
        for i, (orig_idx, track_path) in enumerate(matches, 1):
            print(f"{i}. {os.path.basename(track_path)}")
        
        # Prompt for selection with multi-select option
        print("\nOptions:")
        print("  Enter track number to add a single track")
        print("  Enter multiple numbers separated by commas (e.g. 1,3,5)")
        print("  Enter 'all' to add all tracks")
        print("  Enter 'c' to cancel")
        
        choice = input("\nYour selection: ").strip().lower()
        
        if choice == 'c':
            print("Selection canceled")
            return
        
        if choice == 'all':
            # Add all matching tracks
            added_count = 0
            for _, track_path in matches:
                if self.player.add_to_playlist(playlist_name, track_path):
                    added_count += 1
            
            print(f"Added {added_count} tracks to playlist: {playlist_name}")
            return
        
        # Process comma-separated numbers
        try:
            # Split by comma and convert to integers
            selection_indices = [int(x.strip()) for x in choice.split(',') if x.strip()]
            
            # Validate and add selected tracks
            added_count = 0
            for idx in selection_indices:
                if 1 <= idx <= len(matches):
                    _, track_path = matches[idx - 1]
                    if self.player.add_to_playlist(playlist_name, track_path):
                        added_count += 1
                else:
                    print(f"Invalid selection: {idx}")
            
            if added_count > 0:
                print(f"Added {added_count} track(s) to playlist: {playlist_name}")
        except ValueError:
            print("Invalid input. Please enter track numbers separated by commas.")

    def remove_from_playlist(self, args):
        """Remove a track from a playlist."""
        if len(args) < 2:
            print("Usage: rmfrom <playlist_name> <track_number>")
            return
        
        playlist_name = args[0]
        
        if not args[1].isdigit():
            print("Track number must be a number")
            return
        
        track_num = int(args[1])
        
        if playlist_name in self.player.user_playlists:
            tracks = self.player.user_playlists[playlist_name]['tracks']
            if 1 <= track_num <= len(tracks):
                track_idx = track_num - 1
                track_name = os.path.basename(tracks[track_idx])
                if self.player.remove_from_playlist(playlist_name, track_idx):
                    print(f"Removed '{track_name}' from playlist: {playlist_name}")
            else:
                print(f"Invalid track number. Must be between 1 and {len(tracks)}")
        else:
            print(f"Playlist not found: {playlist_name}")

    def save_current_track(self, args):
        """Quickly save the current track to a playlist."""
        if not self.player.current_track:
            print("No track is currently playing")
            return
        
        if not args:
            # Show available playlists
            print("\nAvailable playlists:")
            for i, name in enumerate(self.player.user_playlists.keys(), 1):
                print(f"{i}. {name}")
            
            # Prompt for selection
            choice = input("\nEnter playlist number or name to save to, or Enter to cancel: ")
            if not choice:
                return
                
            # Convert number to playlist name if needed
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(self.player.user_playlists):
                    playlist_name = list(self.player.user_playlists.keys())[idx]
                else:
                    print("Invalid playlist number")
                    return
            else:
                playlist_name = choice
        else:
            playlist_name = args[0]
        
        # Add current track to the selected playlist
        track_name = os.path.basename(self.player.current_track)
        if self.player.add_to_playlist(playlist_name, self.player.current_track):
            print(f"Added '{track_name}' to playlist: {playlist_name}")
        else:
            print(f"Failed to add track to playlist: {playlist_name}")
            
    def toggle_shuffle(self, args):
        """Toggle shuffle mode on/off."""
        status = self.player.toggle_shuffle()
        print(f"Shuffle mode {status}")
    

    def show_now_playing(self, args):
        """Display a real-time now playing screen with progress bar."""
        # Get current playback information
        playback = self.player.get_current_playback()
        
        # Check if anything is playing
        if playback['state'] not in ['PLAYING', 'PAUSED']:
            print("Nothing is currently playing.")
            return
        
        try:
            # Flag to signal the display thread to exit
            exit_flag = threading.Event()
            
            # Create a simple thread to update the display without blocking
            def update_display(event_data=None):
                if exit_flag.is_set():
                    return
                    
                # Get updated playback info - even if called from an event
                playback = self.player.get_current_playback()
                
                # Extract variables for easy reference
                track_name = playback['track_name']
                artist = playback['artist']
                album = playback['album']
                position = playback['position']
                duration = playback['duration']
                source = self.player.plugin_manager.get_plugin_display_name(playback['source'])
                playback_state = playback['state']
                
                # Calculate progress percentage
                progress_percent = 0
                if duration > 0:
                    progress_percent = min(100, (position / duration) * 100)
                
                # Clear screen
                clear_screen()
                
                # Build display
                print("\n=== NOW PLAYING ===")
                print(f"\nTrack: {track_name}")
                if artist:
                    print(f"Artist: {artist}")
                if album:
                    print(f"Album: {album}")
                print(f"Source: {source}")
                print(f"State: {playback_state}")
                print(f"Volume: {int(self.player.volume * 100)}%")
                print(f"Shuffle: {'On' if self.player.shuffle_mode else 'Off'}")
                
                # Progress bar (50 characters wide)
                bar_width = 50
                filled_width = int(bar_width * progress_percent / 100)
                bar = '█' * filled_width + '░' * (bar_width - filled_width)
                
                # Time display
                position_str = self.format_time(position)
                duration_str = self.format_time(duration)
                
                print(f"\n{position_str} {bar} {duration_str}")
                
                # Show controls
                print("\nControls:")
                print("  [Space] Pause/Play")
                print("  [←/→] Previous/Next Track")
                print("  [↑/↓] Volume Up/Down")
                print("  [s] Toggle Shuffle Mode")
                print("  [q] Return to main menu")
                
                print("\nPress a key...", end='', flush=True)
            
            # Update position handler (only updates the progress bar)
            def update_position(event_data=None):
                if exit_flag.is_set():
                    return
                # For future implementation - could make a more efficient position update
                # without clearing the screen
            
            # Subscribe to events for more responsive updates
            if hasattr(self.player, 'event_bus'):
                self.player.event_bus.subscribe(self.player.STATE_CHANGED, update_display)
                self.player.event_bus.subscribe(self.player.TRACK_CHANGED, update_display)
                self.player.event_bus.subscribe(self.player.POSITION_CHANGED, update_position)
            
            # Initial display
            update_display()
            
            # Start a background thread for regular updates
            def display_loop():
                while not exit_flag.is_set():
                    update_display()
                    time.sleep(0.5)
            
            display_thread = threading.Thread(target=display_loop)
            display_thread.daemon = True
            display_thread.start()
            
            # Main thread handles input
            while True:
                key = readchar.readkey()
                
                # Handle exit command
                if key == 'q':
                    print("\nReturning to main menu...")
                    exit_flag.set()
                    
                    # Unsubscribe from events
                    if hasattr(self.player, 'event_bus'):
                        self.player.event_bus.unsubscribe(self.player.STATE_CHANGED, update_display)
                        self.player.event_bus.unsubscribe(self.player.TRACK_CHANGED, update_display)
                        self.player.event_bus.unsubscribe(self.player.POSITION_CHANGED, update_position)
                    
                    display_thread.join(timeout=1.0)
                    break
                
                # Get active plugin info once for all commands
                active_plugin = self.player.plugin_manager.get_active_plugin()
                current_playback = self.player.plugin_manager.get_playback_info()
                
                # Helper function to get plugin instance if available
                def get_plugin_instance():
                    plugin_info = self.player.plugins.get(active_plugin)
                    if plugin_info and 'instance' in plugin_info:
                        return plugin_info['instance']
                    return None
                
                # Handle different key commands
                if key == readchar.key.SPACE:
                    if active_plugin == 'local':
                        # Toggle local playback using playback state instead of direct enum access
                        if current_playback['state'] == 'PLAYING':
                            self.player.pause()
                        else:
                            self.player.play()
                    else:
                        plugin = get_plugin_instance()
                        if plugin:
                            command = 'pause' if current_playback['state'] == 'PLAYING' else 'play'
                            self.plugin_command(plugin, active_plugin, [command])
                
                elif key == 's':
                    self.player.toggle_shuffle()
                
                elif key in (readchar.key.LEFT, readchar.key.RIGHT):
                    if active_plugin == 'local':
                        args = ""
                        self.previous_track(args) if key == readchar.key.LEFT else self.next_track(args)
                    else:
                        plugin = get_plugin_instance()
                        if plugin:
                            command = 'prev' if key == readchar.key.LEFT else 'next'
                            self.plugin_command(plugin, active_plugin, [command])
                
                elif key in (readchar.key.UP, readchar.key.DOWN):
                    # Calculate new volume based on key
                    volume_change = 0.05 if key == readchar.key.UP else -0.05
                    new_vol = max(0.0, min(1.0, self.player.volume + volume_change))
                    
                    # Apply volume change
                    if active_plugin == 'local':
                        self.player.set_volume(new_vol)
                    else:
                        plugin = get_plugin_instance()
                        if plugin:
                            try:
                                self.plugin_command(plugin, active_plugin, ['volume', str(int(new_vol * 100))])
                                self.player.set_volume(new_vol)
                            except Exception as e:
                                log.info(f"Error setting volume: {e}")
                
        except KeyboardInterrupt:
            print("\nReturning to main menu...")
            # Make sure to stop the display thread if we get an interruption
            if 'exit_flag' in locals():
                exit_flag.set()
                
                # Unsubscribe from events if subscribed
                if hasattr(self.player, 'event_bus'):
                    self.player.event_bus.unsubscribe(self.player.STATE_CHANGED, update_display)
                    self.player.event_bus.unsubscribe(self.player.TRACK_CHANGED, update_display)
                    self.player.event_bus.unsubscribe(self.player.POSITION_CHANGED, update_position)
                
                if 'display_thread' in locals():
                    display_thread.join(timeout=1.0)

    def format_time(self, seconds):
        """Format seconds into mm:ss format."""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _add_search_results_to_playlist(self, matches):
        """Add search results to a selected playlist."""
        # Show available playlists
        print("\nAvailable playlists:")
        for i, name in enumerate(self.player.user_playlists.keys(), 1):
            print(f"{i}. {name}")
        
        playlist_choice = input("\nEnter playlist number or name to add to, or Enter to cancel: ")
        if not playlist_choice:
            return None
        
        # Convert number to playlist name if needed
        if playlist_choice.isdigit():
            idx = int(playlist_choice) - 1
            if 0 <= idx < len(self.player.user_playlists):
                playlist_name = list(self.player.user_playlists.keys())[idx]
            else:
                print("Invalid playlist number")
                return None
        else:
            playlist_name = playlist_choice
        
        # Add all search results to the selected playlist
        added_count = 0
        for _, track_path in matches:
            if self.player.add_to_playlist(playlist_name, track_path):
                added_count += 1
        
        print(f"Added {added_count} tracks to playlist: {playlist_name}")
        return True
         
    def search_tracks(self, args):
        """Search for tracks matching a search term."""
        if not args:
            print("Usage: search <search_term> [--strict]")
            print("  --strict: Enable case-sensitive matching")
            return
        
        if not self.player.playlist:
            print("No tracks loaded. Use 'load <directory>' to load tracks first.")
            return
        
        # Check for strict mode flag
        strict_mode = False
        filtered_args = []
        
        for arg in args:
            if arg.lower() == '--strict':
                strict_mode = True
            else:
                filtered_args.append(arg)
        
        # If all args were flags, show usage
        if not filtered_args:
            print("Usage: search <search_term> [--strict]")
            return
        
        # Combine remaining arguments into one search term
        search_term = ' '.join(filtered_args)
        
        # Don't convert to lowercase if in strict mode
        if not strict_mode:
            search_term = search_term.lower()
        
        print(f"\nSearching for '{search_term}' in {len(self.player.playlist)} tracks...")
        if strict_mode:
            print("(Case-sensitive mode enabled)")
        
        # Find matches
        matches = []
        for i, track_path in enumerate(self.player.playlist):
            track_name = os.path.basename(track_path)
            
            # Convert track name to lowercase only if not in strict mode
            if not strict_mode:
                track_name = track_name.lower()
            
            # Check for match
            if search_term in track_name:
                matches.append((i, track_path))
        
        # Display results
        if not matches:
            print(f"No tracks found matching '{search_term}'")
            return
        
        # Define play action callback
        def play_selected_track(item):
            index, track_path = item
            self.player.current_index = index
            self.player.play()
        
        # Define custom actions
        custom_actions = {
            'a': ('Add results to a playlist', 
                lambda: self._add_search_results_to_playlist(matches))
        }
        
        # Use the simplified pagination function
        self.get_paginated_selection(
            items=matches,
            title=f"Search results for '{search_term}'",
            play_action=play_selected_track,
            custom_actions=custom_actions
        )
                
    def get_paginated_selection(self, items, title="Items", play_action=None, custom_actions=None):
        """
        Utility method that plugins can use to display paginated lists.
        
        Args:
            items: List of items to paginate
            title: Title to display in the header
            play_action: Function to call when an item is selected with Enter (receives selected item)
            custom_actions: Dictionary of key -> (display_name, function) for special keys
        
        Returns:
            Selected item or None if canceled
        """
        if not items:
            print(f"No {title.lower()} to display")
            return None
        
        # Custom formatter for items
        def item_formatter(i, item, is_current, is_selected):
            selector = "→ " if is_selected else "  "
            # If item is a tuple/list, assume first element is display text
            if isinstance(item, (tuple, list)):
                display_text = item[0]
            else:
                display_text = str(item)
            return f"{selector}{i}. {display_text}"
        
        # Create footer with base and custom actions
        def footer(page, total_pages):
            print(f"\nPage {page}/{total_pages} - Options:")
            print("  → / ← - Next/Previous page")
            print("  ↑ / ↓ - Move selector")
            
            if play_action:
                print("  Enter - Select item")
                
            # Add custom actions to footer
            if custom_actions:
                for key, (display_name, _) in custom_actions.items():
                    print(f"  {key} - {display_name}")
                    
            print("  c - Cancel")
        
        # Show paginated list
        result = self.paginate_items(
            items,
            header=lambda page, total: print(f"\n{title} ({len(items)}) - Page {page}/{total}:"),
            footer=footer,
            item_formatter=item_formatter
        )
        
        if result is None:
            return None  # User canceled
        
        # If result is a special key and we have custom actions
        if isinstance(result, str) and custom_actions and result in custom_actions:
            _, action_function = custom_actions[result]
            return action_function()
            
        # If normal selection and we have a play action
        if not isinstance(result, str) and play_action:
            selected_item = items[result]
            play_action(selected_item)
            return selected_item
            
        # Just return the selected item/key
        if isinstance(result, str):
            return result
        else:
            return items[result]
            
    def paginate_items(self, items, page_size=20, header=None, footer=None, item_formatter=None, 
                  current_index=None, play_callback=None, custom_actions=None, title=None):
        """
        Display items with pagination and handle user interaction using arrow keys.
        
        Args:
            items: List of items to paginate
            page_size: Number of items per page (default: 20)
            header: Function that takes page number and total pages to display header
            footer: Function that takes page number and total pages to display footer
            item_formatter: Function that takes (index, item, is_current, is_selected) and returns formatted string
            current_index: Index of current item (for highlighting)
            play_callback: Function to call when an item is selected (receives selected item)
            custom_actions: Dictionary of key -> (display_name, function) for special keys
            title: Title to display at the top of the pagination
        
        Returns:
            Selected item or None if canceled
        """        
        if not items:
            print("No items to display")
            return None
        
        # Initialize custom_actions if None
        if custom_actions is None:
            custom_actions = {}
        
        # Default header function
        if header is None:
            def header(page, total_pages):
                if title:
                    print(f"\n{title}")
                print(f"\nShowing page {page}/{total_pages} ({len(items)} items)")
        
        # Default footer function
        if footer is None:
            def footer(page, total_pages):
                print("\nNavigation:")
                print("  → / ← - Next/Previous page")
                print("  ↑ / ↓ - Move selector")
                print("  Enter - Select item")
                
                # Add custom actions to footer
                for key, (action_name, _) in custom_actions.items():
                    print(f"  {key} - {action_name}")
                    
                print("  c - Cancel")
        
        # Default item formatter - Check if items are tuples/lists (from plugins)
        if item_formatter is None:
            def item_formatter(i, item, is_current, is_selected):
                current_marker = " *" if is_current else ""
                selector = "→ " if is_selected else "  "
                
                # Check if this is a plugin result (tuple/list with title as first element)
                if isinstance(item, (tuple, list)) and len(item) > 0:
                    # Use only the title (first element) for display
                    display_item = item[0]
                else:
                    display_item = item
                    
                return f"{selector}{i}. {display_item}{current_marker}"
        
        total_pages = (len(items) + page_size - 1) // page_size
        current_page = 1
        
        # Cursor position within the current page
        self.paginate_cursor_position = 0
        
        while True:
            # Calculate slice for current page
            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, len(items))
            
            # Number of items on the current page
            items_on_page = end_idx - start_idx
            
            # Make sure cursor position is valid for current page
            if self.paginate_cursor_position >= items_on_page:
                self.paginate_cursor_position = items_on_page - 1
            
            # Clear screen and show header
            clear_screen()
            
            # Display header
            header(current_page, total_pages)
            
            # Display items for current page
            for i in range(start_idx, end_idx):
                # Calculate display index (1-based) and position within page (0-based)
                display_idx = i + 1
                page_position = i - start_idx
                
                # Check if this is the current item
                is_current = current_index is not None and i == current_index
                
                # Check if this is the selected item (cursor position)
                is_selected = page_position == self.paginate_cursor_position
                
                # Format and print item
                print(item_formatter(display_idx, items[i], is_current, is_selected))
            
            # Display footer
            footer(current_page, total_pages)
            
            print("\nWaiting for key press...")
            
            # Get key press
            key = readchar.readkey()
            
            # Handle navigation with arrow keys
            if key == readchar.key.RIGHT:
                if current_page < total_pages:
                    current_page += 1
                    self.paginate_cursor_position = 0  # Reset cursor position on page change
                else:
                    print("Already on the last page")
            
            elif key == readchar.key.LEFT:
                if current_page > 1:
                    current_page -= 1
                    self.paginate_cursor_position = 0  # Reset cursor position on page change
                else:
                    print("Already on the first page")
            
            # Handle cursor movement
            elif key == readchar.key.UP:
                if self.paginate_cursor_position > 0:
                    self.paginate_cursor_position -= 1
                else:
                    # Wrap to bottom if at top
                    self.paginate_cursor_position = items_on_page - 1
            
            elif key == readchar.key.DOWN:
                if self.paginate_cursor_position < items_on_page - 1:
                    self.paginate_cursor_position += 1
                else:
                    # Wrap to top if at bottom
                    self.paginate_cursor_position = 0
            
            # Handle select with Enter
            elif key == readchar.key.ENTER:
                # Calculate the absolute index in the items list
                selected_index = start_idx + self.paginate_cursor_position
                selected_item = items[selected_index]
                
                # Execute callback if provided
                if play_callback:
                    play_callback(selected_item)
                
                return selected_item
            
            # Handle cancel
            elif key.lower() == 'c':
                return None
            
            # Handle custom actions
            elif key.lower() in custom_actions:
                action_name, action_func = custom_actions[key.lower()]
                
                # Execute the custom action
                result = action_func()
                
                # If action returns something, return it
                if result is not None:
                    return result
            
            # Return special keys for command handling in caller functions
            elif key.lower() in ['a', 'l', 's', 'h']:
                return key.lower()
            
            else:
                # Ignore other keys
                pass
    
    def get_paginated_selection(self, items, title=None, play_action=None, custom_actions=None):
        """
        Handle paginated selection for both native and plugin functions.
        
        Args:
            items: List of items to display
            title: Title to display at the top of the pagination
            play_action: Function to call when an item is selected (receives selected item)
            custom_actions: Dictionary of key -> (display_name, function) for special keys
        
        Returns:
            Selected item or None if canceled
        """
        # Reset cursor position to 0 before starting pagination
        self.paginate_cursor_position = 0
        
        return self.paginate_items(
            items=items,
            title=title,
            play_callback=play_action,
            custom_actions=custom_actions
        )
                
    def show_settings_menu(self, args):
        """Show and manage player settings."""
        while True:
            clear_screen()
            print("\n=== Settings Menu ===")
            print("1. Plugin Settings")
            print("2. Player Information")
            print("3. Return to Main Menu")
            
            choice = input("\nEnter your choice (1-3): ")
            
            if choice == '1':
                self.manage_plugins([])
            elif choice == '2':
                self.show_player_info()
            elif choice == '3' or not choice:
                return
            else:
                print("Invalid choice")
                time.sleep(1)
    
    def show_player_info(self):
        """Show information about the player."""
        clear_screen()
        print("\n=== Player Information ===")
        
        # Get status info from the playback_info directly
        playback = self.player.get_current_playback()
        status = self.player.get_status()
        
        # Player version
        print("Simple Python Music Player")
        print("\nSettings:")
        print(f"- Music Library: {self.player.MUSIC_LIBRARY_PATH or 'Not set'}")
        print(f"- Scan Subdirectories: {self.player.SCAN_SUBDIRECTORIES}")
        print(f"- Default Sort: {self.player.DEFAULT_SORT}")
        print(f"- Shuffle Mode: {status['shuffle']}")
        print(f"- Playlists Path: {self.player.PLAYLISTS_PATH}")
        print(f"- Plugins Path: {self.player.PLUGINS_PATH}")
        print(f"- Auto-load Plugins: {status['auto_load_plugins']}")
        print(f"- Current Playback State: {playback['state']}")
        print(f"- Current Source: {playback['source']}")
        print(f"- Enabled Plugins: {len(self.player.plugin_manager.settings['enabled_plugins'])}")
        print(f"- Available Plugins: {len(self.player.available_plugins)}")
        print(f"- Current Volume: {int(status['volume'] * 100)}%")
        
        input("\nPress Enter to return to Settings Menu...")
    
    def manage_plugins(self, args):
        """Manage plugin settings."""
        while True:
            # Rescan available plugins
            available_plugins = self.player.scan_plugins()
            
            clear_screen()
            print("\n=== Plugin Management ===")
            
            # Show auto-load setting
            auto_load = self.player.plugin_manager.settings['auto_load_plugins']
            print(f"Auto-load plugins: {'Enabled' if auto_load else 'Disabled'}")
            
            # Show available plugins and their status
            print("\nAvailable Plugins:")
            if not available_plugins:
                print("No plugins found in plugins directory")
            else:
                for i, (name, info) in enumerate(available_plugins.items(), 1):
                    enabled = name in self.player.plugin_manager.settings['enabled_plugins']
                    loaded = info['loaded']
                    status = f"{'Enabled' if enabled else 'Disabled'}"
                    if enabled:
                        status += f", {'Loaded' if loaded else 'Not loaded'}"
                    print(f"{i}. {name} - {status}")
            
            print("\nOptions:")
            print("1. Toggle auto-load plugins")
            print("2. Enable/disable a plugin")
            print("3. Reload plugins")
            print("4. Return to Settings Menu")
            
            choice = input("\nEnter your choice (1-4): ")
            
            if choice == '1':
                # Toggle auto-load setting
                auto_load = not auto_load
                self.player.set_auto_load_plugins(auto_load)
                print(f"Auto-load plugins: {'Enabled' if auto_load else 'Disabled'}")
                time.sleep(1)
                
            elif choice == '2':
                if not available_plugins:
                    print("No plugins available to enable/disable")
                    time.sleep(1)
                    continue
                    
                # Ask which plugin to toggle
                plugin_choice = input("\nEnter plugin number to toggle, or Enter to cancel: ")
                if not plugin_choice or not plugin_choice.isdigit():
                    continue
                    
                plugin_idx = int(plugin_choice) - 1
                if 0 <= plugin_idx < len(available_plugins):
                    # Get the plugin name
                    plugin_name = list(available_plugins.keys())[plugin_idx]
                    
                    # Check if currently enabled
                    is_enabled = plugin_name in self.player.plugin_manager.settings['enabled_plugins']
                    
                    if is_enabled:
                        # Disable plugin
                        if self.player.disable_plugin(plugin_name):
                            print(f"Disabled plugin: {plugin_name}")
                            
                            # Publish source changed event if this was the active plugin
                            if hasattr(self.player, 'event_bus') and self.player.plugin_manager.get_active_plugin() == plugin_name:
                                self.player.event_bus.publish(self.player.SOURCE_CHANGED, {
                                    'previous_source': plugin_name,
                                    'new_source': 'local'
                                })
                    else:
                        # Enable plugin
                        if self.player.enable_plugin(plugin_name):
                            print(f"Enabled plugin: {plugin_name}")
                            
                            # If plugin was enabled, update command list
                            self.add_plugin_commands()
                    
                    time.sleep(1)
                else:
                    print("Invalid plugin number")
                    time.sleep(1)
                    
            elif choice == '3':
                # Reload all enabled plugins
                print("Reloading plugins...")
                loaded_count = self.player.load_plugins()
                print(f"Loaded {loaded_count} plugins")
                
                # Update commands
                self.add_plugin_commands()
                
                time.sleep(1)
                
            elif choice == '4' or not choice:
                return
                
            else:
                print("Invalid choice")
                time.sleep(1)
                
    def run(self):
        """Run the command-line interface"""
        print("=== Simple Python Music Player ===")
        print("Type 'help' for available commands")
        
        while True:
            try:
                # Get current playback info from playback_info rather than direct state access
                playback = self.player.get_current_playback()
                
                # Show track status indicator if there is a current track
                if playback['track_name']:
                    source_name = self.player.plugin_manager.get_plugin_display_name(playback['source'])
                    artist_str = f" - {playback['artist']}" if playback['artist'] else ""
                    
                    # Show different status indicators based on state string
                    if playback['state'] == 'PLAYING':
                        status_icon = "|>"  # Play icon
                    elif playback['state'] == 'PAUSED':
                        status_icon = "||"  # Pause icon
                    else:  # STOPPED
                        status_icon = "[]"  # Stop icon
                    
                    print(f"\n{status_icon} {playback['track_name']}{artist_str} ({source_name})")
                    
                command = input("\n> ").strip()
                if not command:
                    continue
                
                parts = command.split()
                cmd = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []
                
                if cmd in self.commands:
                    self.commands[cmd](args)
                else:
                    print(f"Unknown command: {cmd}")
                    print("Type 'help' for available commands")
            
            except KeyboardInterrupt:
                print("\nExiting...")
                self.exit([])
            except Exception as e:
                print(f"Error: {e}")