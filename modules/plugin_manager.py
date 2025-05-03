# plugin_manager.py
import os
import importlib.util
import json
from modules.logging_utils import log_function_call, app_logger as log
from datetime import datetime


class PluginManager:
    """Manages all plugins and their states"""
    
    def __init__(self, settings_file="plugin_settings.json", player_instance=None):
        """Initialize the plugin manager"""
        self.player = player_instance
        self.event_bus = player_instance.event_bus if player_instance else None
        self.plugins = {}  # Store all loaded plugins
        self.available_plugins = {}  # Store information about available plugins
        self.active_plugin = None  # Currently active plugin
        self.settings_file = settings_file
        self.settings = {
            'auto_load_plugins': True,  
            'enabled_plugins': []  # List of enabled plugin names
        }
        # Load settings if the file exists
        self.load_settings()
        self.get_info_time: datetime = None
    
    def load_settings(self):
        """Load plugin settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    self.settings = json.load(f)
            else: 
                with open(self.settings_file, 'w') as f:
                    json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error loading plugin settings: {e}")
    
    def save_settings(self):
        """Save plugin settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            print(f"Saved plugin settings to {self.settings_file}")
            return True
        except Exception as e:
            print(f"Error saving plugin settings: {e}")
            return False
    
    def scan_plugin_directory(self, plugins_dir):
        """
        Scan the plugins directory for available plugins without loading them
        """
        self.available_plugins = {}
        
        # Create plugins directory if it doesn't exist
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
            return self.available_plugins
            
        # Find each Python file in the plugins directory
        for filename in os.listdir(plugins_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                plugin_name = filename[:-3]  # Remove .py extension
                module_path = os.path.join(plugins_dir, filename)
                
                # Check if it's already loaded
                is_loaded = plugin_name in self.plugins
                
                # Store basic information about the plugin
                self.available_plugins[plugin_name] = {
                    'name': plugin_name,
                    'path': module_path,
                    'enabled': plugin_name in self.settings['enabled_plugins'],
                    'loaded': is_loaded
                }
        
        return self.available_plugins
    
    def load_plugin(self, plugin_name, plugin_path, player_instance):
        """Load a specific plugin by name"""
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # If the module has a Plugin class, initialize it
            if hasattr(module, 'Plugin'):
                plugin = module.Plugin(player_instance)
                # Register with the plugin manager
                self.register_plugin(plugin_name, plugin)
                
                # Subscribe to events if event bus exists
                if hasattr(self.player, 'event_bus'):
                    # Standard player events
                    for event_type, handler_name in [
                        (self.player.STATE_CHANGED, 'on_state_changed'),
                        (self.player.TRACK_CHANGED, 'on_track_changed'),
                        (self.player.SOURCE_CHANGED, 'on_source_changed'),
                        (self.player.POSITION_CHANGED, 'on_position_changed'),
                        (self.player.VOLUME_CHANGED, 'on_volume_changed'),
                        # Legacy events for backward compatibility
                        ('on_play', 'on_play'),
                        ('on_pause', 'on_pause'),
                        ('on_stop', 'on_stop'),
                        ('on_playlist_loaded', 'on_playlist_loaded'),
                        ('on_volume_change', 'on_volume_change'),
                        ('on_shutdown', 'on_shutdown')
                    ]:
                        if hasattr(plugin, handler_name):
                            self.player.event_bus.subscribe(event_type, getattr(plugin, handler_name))
                
                # Update available plugins info
                if plugin_name in self.available_plugins:
                    self.available_plugins[plugin_name]['loaded'] = True
                print(f"Loaded plugin: {plugin_name}")
                return True
            else:
                print(f"Plugin {plugin_name} does not have a Plugin class")
                return False
        except Exception as e:
            print(f"Error loading plugin {plugin_name}: {e}")
            return False
    
    def load_enabled_plugins(self, plugins_dir, player_instance):
        """
        Load all enabled plugins from the plugins directory
        
        Args:
            plugins_dir: Directory containing plugin files
            player_instance: Reference to the music player instance
            
        Returns:
            int: Number of plugins loaded successfully
        """
        # First scan to find available plugins
        self.scan_plugin_directory(plugins_dir)
        
        loaded_count = 0
        for plugin_name, plugin_info in self.available_plugins.items():
            # Only load enabled plugins that aren't already loaded
            if plugin_name in self.settings['enabled_plugins'] and not plugin_info['loaded']:
                if self.load_plugin(plugin_name, plugin_info['path'], player_instance):
                    # Update loaded status
                    self.available_plugins[plugin_name]['loaded'] = True
                    loaded_count += 1
                    
        return loaded_count
    
    def enable_plugin(self, plugin_name):
        """
        Enable a plugin by adding it to the enabled_plugins list
        
        Returns:
            bool: True if the plugin was enabled, False otherwise
        """
        if plugin_name not in self.available_plugins:
            print(f"Plugin {plugin_name} is not available")
            return False
        
        if plugin_name not in self.settings['enabled_plugins']:
            self.settings['enabled_plugins'].append(plugin_name)
            self.save_settings()
            return True
            
        return False  # Already enabled
    
    def disable_plugin(self, plugin_name):
        """Disable a plugin by removing it from the enabled_plugins list"""
        if plugin_name in self.settings['enabled_plugins']:
            self.settings['enabled_plugins'].remove(plugin_name)
            self.save_settings()
            
            # If this plugin is active, reset to local playback
            is_active = self.active_plugin == plugin_name
            if is_active:
                # Publish source changed event before actually changing
                if hasattr(self.player, 'event_bus'):
                    self.player.event_bus.publish(self.player.SOURCE_CHANGED, {
                        'previous_source': plugin_name,
                        'new_source': 'local'
                    })
                
            # Remove from loaded plugins
            if plugin_name in self.plugins:
                # Get plugin instance
                plugin_instance = self.plugins[plugin_name]['instance']
                
                # Unsubscribe from all events if event_bus exists
                if hasattr(self.player, 'event_bus'):
                    # Unsubscribe from standard events
                    for event_type in [
                        self.player.STATE_CHANGED,
                        self.player.TRACK_CHANGED,
                        self.player.SOURCE_CHANGED,
                        self.player.POSITION_CHANGED,
                        self.player.VOLUME_CHANGED,
                        'on_play', 'on_pause', 'on_stop', 'on_playlist_loaded', 
                        'on_volume_change', 'on_shutdown'
                    ]:
                        handler_name = event_type
                        if event_type == self.player.STATE_CHANGED:
                            handler_name = 'on_state_changed'
                        elif event_type == self.player.TRACK_CHANGED:
                            handler_name = 'on_track_changed'
                        elif event_type == self.player.SOURCE_CHANGED:
                            handler_name = 'on_source_changed'
                        elif event_type == self.player.POSITION_CHANGED:
                            handler_name = 'on_position_changed'
                        elif event_type == self.player.VOLUME_CHANGED:
                            handler_name = 'on_volume_changed'
                            
                        if hasattr(plugin_instance, handler_name):
                            self.player.event_bus.unsubscribe(event_type, getattr(plugin_instance, handler_name))
                
                # Call shutdown method if it exists
                if hasattr(plugin_instance, 'on_shutdown'):
                    try:
                        plugin_instance.on_shutdown({})
                    except Exception as e:
                        print(f"Error shutting down plugin {plugin_name}: {e}")
                        
                # Remove from plugins dictionary
                del self.plugins[plugin_name]
                
                # Update available plugins status
                if plugin_name in self.available_plugins:
                    self.available_plugins[plugin_name]['loaded'] = False
                
                # After removing the plugin, actually clear active if needed
                if is_active:
                    self.clear_active_plugin()
                    
                return True
                
            return False  # Not enabled
    
    def set_auto_load(self, enabled):
        """Set whether plugins should be automatically loaded"""
        self.settings['auto_load_plugins'] = enabled
        self.save_settings()
        return True
    
    def register_plugin(self, plugin_name, plugin_instance):
        """Register a plugin with the manager"""
        self.plugins[plugin_name] = {
            'instance': plugin_instance,
            'name': plugin_instance.name if hasattr(plugin_instance, 'name') else plugin_name,
            'command_name': plugin_instance.command_name if hasattr(plugin_instance, 'command_name') else plugin_name.lower()
        }
        # Update available plugins status
        if plugin_name in self.available_plugins:
            self.available_plugins[plugin_name]['loaded'] = True
        return True
    
    def set_active_plugin(self, plugin_name):
        """Set the currently active plugin"""
        previous_plugin = self.active_plugin
        
        if plugin_name == 'local':
            self.active_plugin = plugin_name
            self.player.playback_info['source'] = plugin_name
            self.player.playback_info['plugin_instance'] = None
            
            # Publish source changed event
            if hasattr(self.player, 'event_bus') and previous_plugin != plugin_name:
                self.player.event_bus.publish(self.player.SOURCE_CHANGED, {
                    'previous_source': previous_plugin,
                    'new_source': plugin_name
                })
            return True
        elif plugin_name in self.plugins:
            self.active_plugin = plugin_name
            self.player.playback_info['source'] = plugin_name
            self.player.playback_info['plugin_instance'] = self.plugins[plugin_name]['instance']
            
            # Publish source changed event
            if hasattr(self.player, 'event_bus') and previous_plugin != plugin_name:
                self.player.event_bus.publish(self.player.SOURCE_CHANGED, {
                    'previous_source': previous_plugin,
                    'new_source': plugin_name
                })
            return True
        return False
    
    def clear_active_plugin(self):
        """Clear the active plugin (set to local)"""
        old_source = self.active_plugin
        self.active_plugin = 'local'
        self.player.playback_info['source'] = 'local'
        self.player.playback_info['plugin_instance'] = None
        
        # Publish source changed event if it's actually changing
        if hasattr(self.player, 'event_bus') and old_source != 'local':
            self.player.event_bus.publish(self.player.SOURCE_CHANGED, {
                'previous_source': old_source,
                'new_source': 'local'
            })

    def reset_playback_info_time(self):
        """Reset the timestamp for playback info fetching"""
        self.get_info_time = None
    
    def get_playback_info(self):
        """Get current playback information"""
        # If an external plugin is active, try to get updated info        
        current_info = self.player.playback_info.copy()
        if self.active_plugin != 'local' and self.active_plugin in self.plugins and current_info['state'] == 'PLAYING':
            plugin = self.plugins[self.active_plugin]['instance']
            if hasattr(plugin, 'get_current_playback'):
                try:
                    plugin_info = plugin.get_current_playback()
                    if plugin_info:
                        # Check for state change (playing/paused)
                        state_changed = False
                        new_state = 'PLAYING' if plugin_info.get('is_playing', False) else 'PAUSED'
                        if new_state != current_info['state']:
                            state_changed = True
                        
                        # Check for track change
                        track_changed = False
                        new_track = plugin_info.get('track_name', 'Unknown Track')
                        if new_track != current_info['track_name']:
                            track_changed = True
                        
                        # Update stored info with latest from plugin
                        updated_info = {
                            'track_name': new_track,
                            'artist': plugin_info.get('artist', ''),
                            'album': plugin_info.get('album', ''),
                            'position': plugin_info.get('progress_ms', 0) / 1000.0 if 'progress_ms' in plugin_info else plugin_info.get('position', 0),
                            'duration': plugin_info.get('duration_ms', 0) / 1000.0 if 'duration_ms' in plugin_info else plugin_info.get('duration', 0),
                            'genre': plugin_info.get('genre', ''),
                            'year': plugin_info.get('year', ''),
                            'state': new_state
                        }
                        
                        # Update the player's playback info
                        self.player.update_playback_info(updated_info)
                        
                        # Detect position change for position event
                        if hasattr(self.player, 'event_bus'):
                            if abs(updated_info['position'] - current_info.get('position', 0)) > 1.0:
                                self.player.event_bus.publish(self.player.POSITION_CHANGED, {
                                    'position': updated_info['position'],
                                    'duration': updated_info['duration']
                                })
                        
                        if self.get_info_time is None:
                            self.get_info_time = datetime.now()
                except Exception as e:
                    print(f"Error getting playback info from plugin {self.active_plugin}: {e}")
        
        return self.player.playback_info
    
    def is_plugin_playing(self, plugin_name):
        """Check if a specific plugin is playing"""
        if plugin_name not in self.plugins:
            return False
            
        plugin = self.plugins[plugin_name]['instance']
        if hasattr(plugin, 'is_playing'):
            try:
                return plugin.is_playing()
            except Exception as e:
                print(f"Error checking if plugin {plugin_name} is playing: {e}")
        return False
    
    def get_active_plugin(self):
        """Get the currently active plugin name"""
        return self.active_plugin
    
    def get_plugin_display_name(self, plugin_name):
        """Get a friendly display name for a plugin"""
        if plugin_name == 'local':
            return 'Local'
        elif plugin_name in self.plugins:
            return self.plugins[plugin_name]['name']
        return plugin_name
    
    def get_plugin_command_names(self):
        """Get a dictionary of plugin names to command names"""
        return {name: info['command_name'] for name, info in self.plugins.items()}
    
    def get_all_plugins(self):
        """Get all registered plugins"""
        return self.plugins
    
    def get_available_plugins(self):
        """Get information about available plugins"""
        return self.available_plugins
    
    def ensure_exclusive_playback(self, new_source):
        """
        Ensures that only one source is playing at a time.
        """
        # print(f"Ensuring exclusive playback for {new_source}")
        
        # If current source is already the new source, nothing to do
        if self.active_plugin == new_source:
            return True
        
        # Get current playback info and source
        current_source = self.active_plugin
        current_info = self.player.playback_info.copy()
        
        # Debug info
        print(f"Current active source: {current_source}")
        print(f"Current state: {current_info.get('state')}")
        
        # Force stop all playback regardless of state
        if current_source == 'local':
            # Force stop local playback
            # print("Stopping local playback...")
            stop_result = self.player.media_handler.stop_audio()
            # print(f"Stop audio result: {stop_result}")
            self.player.state = 0  # Directly set to STOPPED (0)
            self.player.update_playback_info({'state': 'STOPPED'})
            
            # Publish events
            if hasattr(self.player, 'event_bus'):
                self.player.event_bus.publish('on_stop', {})
                # Also publish the new standardized event
                self.player.event_bus.publish(self.player.STATE_CHANGED, {
                    'previous_state': current_info.get('state', 'UNKNOWN'),
                    'new_state': 'STOPPED',
                    'source': 'local'
                })
            
            # Verify that playback has stopped
            import time
            time.sleep(0.2)  # Short delay to let audio system respond
            
            # Extra check for pygame
            try:
                import pygame
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    print("WARNING: Pygame still playing after stop - forcing stop again")
                    pygame.mixer.music.stop()
                    time.sleep(0.2)  # Another short delay
                    if pygame.mixer.music.get_busy():
                        print("CRITICAL: Pygame still playing after second stop attempt!")
                else:
                    print("Pygame playback confirmed stopped")
            except Exception as e:
                print(f"Error checking pygame state: {e}")
        
        elif current_source in self.plugins:
            # Force stop the active plugin
            print(f"Stopping plugin {current_source}...")
            plugin_info = self.plugins[current_source]
            if plugin_info and 'instance' in plugin_info:
                plugin = plugin_info['instance']
                if hasattr(plugin, 'stop'):
                    try:
                        plugin.stop([])
                        print(f"Plugin {current_source} stopped via stop method")
                    except Exception as e:
                        print(f"Error stopping plugin {current_source}: {e}")
                elif hasattr(plugin, 'pause'):
                    try:
                        plugin.pause([])
                        print(f"Plugin {current_source} stopped via pause method")
                    except Exception as e:
                        print(f"Error pausing plugin {current_source}: {e}")
        
        # Now set the new active source
        print(f"Setting new active source: {new_source}")
        self.active_plugin = new_source
        self.player.playback_info['source'] = new_source
        
        if new_source != 'local' and new_source in self.plugins:
            self.player.playback_info['plugin_instance'] = self.plugins[new_source]['instance']
        else:
            self.player.playback_info['plugin_instance'] = None
        
        # Publish source changed event
        if hasattr(self.player, 'event_bus'):
            self.player.event_bus.publish(self.player.SOURCE_CHANGED, {
                'previous_source': current_source,
                'new_source': new_source,
            })
        
        print(f"New active source set: {self.active_plugin}")
        return True

    def update_playback_info(self, info):
        """Update playback information"""
        self.player.update_playback_info(info)
