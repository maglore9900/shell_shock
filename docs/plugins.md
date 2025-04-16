# Creating Plugins - Guide

This guide will help you develop custom plugins for the music player system. Plugins extend the player with new functionality, whether it's integration with external services or adding new features.

## Plugin System Overview

The plugin system is built around the `BasePlugin` class which defines a common interface for all plugins. Each plugin must implement a set of standard methods to handle media playback, search, and other functions.

The system supports various types of plugins:

* External service integrations (Spotify, YouTube, etc.)
* Local media playback
* Content providers (podcasts, internet radio, etc.)
* Utility plugins

## Getting Started

### Plugin Structure

Each plugin must:

1. Create a Python file in the `plugins` directory
2. Define a `Plugin` class that inherits from `BasePlugin`
3. Implement required abstract methods
4. Register any custom commands and add pagination commands to `self.paginate_commands` if needed

Here's an example plugin initialization:

```python
def __init__(self, player):
    super().__init__(player)
    self.name = "My Plugin"  # User-friendly name
    self.command_name = player.env("PLUGIN_CMD", default="myplugin")  # CLI command
    self.paginate_commands = ['search', 'list']  # Commands that use pagination
  
    # Other initialization...
    self.initialized = True  # Must set this to True when ready
```

### Minimum Requirements

A basic plugin must implement the following abstract methods:

* `_play_impl(self, args)`: Play media
* `_pause_impl(self, args)`: Pause playback
* `_set_volume_impl(self, volume)`: Adjust volume
* `update_playback_info(self)`: Update the system with current playback info
* `play_track(self, track_data)`: Play a specific track
* `get_current_playback(self)`: Return information about what's playing

### Plugin Template

Use the provided [template_plugin.py](template_plugin.py) template as a starting point for new plugins.

## Key Concepts

### Playback State Management

Plugins must update the player with their playback state using the `update_playback_state_from_info` method. This keeps the central system aware of what's currently playing.

Example:

```python
playback_info = {
    'track_name': 'Song Title',
    'artist': 'Artist Name',
    'album': 'Album Name',
    'position': 30.5,  # seconds
    'duration': 180.0,  # seconds
}
self.update_playback_state_from_info(playback_info)
```

### Exclusive Playback

When a plugin starts playing media, it should ensure that other plugins stop playback:

```python
self.player.plugin_manager.ensure_exclusive_playback(self.plugin_id)
```

### Command Handling

Plugins can define custom commands in the `command_help()` method. These will be accessible through the player's command line interface.

### Pagination Support

The player system includes a powerful pagination system for listing items, search results, and other collections. To use pagination in your plugin:

1. Add command names to the `self.paginate_commands` list (e.g., `self.paginate_commands = ['search', 'list']`)
2. Return results in the format: `[(display_text, item_id, metadata), ...]`

Your command methods should return a list of tuples with this structure:

* `display_text`: String to display for the item
* `item_id`: Identifier for the item (can be index, ID, or other reference)
* `metadata`: Dictionary with any additional information needed to play/use the item

The pagination system provides:

* Arrow key navigation (up/down for selection, left/right for pages)
* Item selection with Enter
* Cancellation with 'c'
* Special key handling ('a', 'l', 's', 'h')
* Current item highlighting

## Handling Media Types

### Processing Pagination Results

Your plugin needs to handle different argument types in `_play_impl()` since it can be called from both direct commands and pagination selection:

```python
def _play_impl(self, args):
    # Handle pagination selection (tuple form)
    if isinstance(args, tuple) and len(args) == 3:
        display_text, item_id, metadata = args
        return self._play_item(item_id, metadata)
      
    # Handle pagination in list form
    if isinstance(args, list) and len(args) == 1 and isinstance(args[0], tuple):
        display_text, item_id, metadata = args[0]
        return self._play_item(item_id, metadata)
      
    # Handle numeric index as string from command line
    if isinstance(args, list) and len(args) == 1 and args[0].isdigit():
        index = int(args[0])
        # Process the index...
      
    # Handle search terms or other arguments
    # ...
```

### Streaming Services

For streaming services like Spotify, implement API calls to control playback:

```python
def _play_impl(self, args):
    # Process args as shown above, then:
    return self.api.play(item_id)

def _pause_impl(self, args):
    return self.api.pause()
```

### Local Audio Files

For plugins that play local files, use the helper methods from BasePlugin:

```python
def _play_impl(self, args):
    file_path = 'path/to/audio.mp3'
    return self.play_audio_file(file_path)[0]

def _pause_impl(self, args):
    return self.pause_audio()
```

## Event Handlers

Plugins can respond to system events by implementing these methods:

* `on_play(self, data)`: When playback starts
* `on_pause(self, data)`: When playback pauses
* `on_stop(self, data)`: When playback stops
* `on_shutdown(self, data)`: When the player is shutting down

## Handling Pagination

The player system includes a `paginate_items` function that displays items with interactive navigation:

```python
# Example usage in a plugin command:
def list(self, args):
    """List available media"""
    # Get items to display
    items = [("Track 1", 1, {"id": "track1"}), 
             ("Track 2", 2, {"id": "track2"})]
  
    # Return items for pagination
    return items
```

The pagination system will:

* Display items with navigation prompts
* Allow users to move through pages with arrow keys
* Highlight the current selection
* Return the selected item when the user presses Enter
* Support special keys for additional actions

Your plugin commands that are listed in `self.paginate_commands` should return data in the format expected by the pagination system.

## Testing Your Plugin

1. Place your plugin in the `plugins` directory
2. Restart the player
3. Your plugin commands should be available via the CLI

## Best Practices

1. **Error Handling** : Always catch and log exceptions to prevent your plugin from crashing the system
2. **Resource Management** : Clean up resources (files, connections) in the `on_shutdown` handler
3. **State Updates** : Keep the plugin manager informed of state changes
4. **Playback Control** : Use the `handle_state_transition` method for standard actions
5. **Configuration** : Use environment variables via `player.env()` for configuration

## Example Plugins

Review the existing plugins for reference implementations:

* `spotify_plugin.py`: Integration with Spotify API
* `podcast_plugin.py`: Podcast feed player
* `youtube_plugin.py`: YouTube audio player

## Advanced Features

### Temporary File Management

For plugins that download content, use the temp file system and clean up properly:

```python
self.temp_dir = tempfile.mkdtemp()
# Later during cleanup
self.cleanup_temp_file()
```

### Custom Commands

Add custom commands by implementing methods on your Plugin class and documenting them in `command_help()`.

## Troubleshooting

* If your plugin isn't recognized, check the constructor initialization
* If playback isn't working, verify that exclusive playback is being requested
* For API integration issues, add more detailed error logging

## Contributing

When creating new plugins:

1. Follow the existing code style
2. Ensure proper error handling
3. Update the help text to document all commands
4. Clean up resources on shutdown

Happy plugin development!
