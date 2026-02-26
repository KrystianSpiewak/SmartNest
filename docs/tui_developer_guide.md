# SmartNest TUI Developer Guide

A comprehensive guide to implementing, testing, and maintaining Terminal User Interface (TUI) screens in SmartNest.

**Last Updated:** February 26, 2026 (Post-TUI Implementation - Week 7)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Screen Implementation Patterns](#screen-implementation-patterns)
3. [Rich Library Patterns](#rich-library-patterns)
4. [MQTT Integration](#mqtt-integration)
5. [HTTP API Integration](#http-api-integration)
6. [Navigation and Keyboard Handling](#navigation-and-keyboard-handling)
7. [Testing Strategies](#testing-strategies)
8. [Performance Optimization](#performance-optimization)

---

## Architecture Overview

### SmartNestTUI Main Application

The `SmartNestTUI` class serves as the main application controller:

```python
class SmartNestTUI:
    """Main TUI application with screen management and lifespan control."""
    
    def __init__(self, api_base_url: str = "http://localhost:8000", mqtt_config: MQTTConfig | None = None):
        # Shared resources
        self.console = Console()                          # Rich console for all screens
        self.http_client = httpx.Client(base_url=api_base_url, timeout=5.0)
        self.mqtt_client = SmartNestMQTTClient(mqtt_config or MQTTConfig())
        
        # Screen instances (created once, reused)
        self.dashboard = DashboardScreen(self.console)
        self.device_list = DeviceListScreen(self.console, self.http_client)
        self.device_detail = DeviceDetailScreen(self.console, self.http_client)
        self.sensor_view = SensorViewScreen(self.console, self.http_client)
        self.settings = SettingsScreen(self.console, self.http_client)
        
        # Navigation state
        self.current_screen = "dashboard"
        self.system_status: dict[str, Any] = {}  # Updated via MQTT
    
    def startup(self) -> None:
        """Initialize MQTT connection, subscribe to system topics."""
        self.mqtt_client.connect()
        self.mqtt_client.subscribe("smartnest/system/status")
        self.mqtt_client.add_topic_handler("smartnest/system/status", self._on_system_status)
    
    def shutdown(self) -> None:
        """Clean disconnect of MQTT and HTTP clients."""
        self.mqtt_client.disconnect()
        self.http_client.close()
```

**Key Design Principles:**
- **Single Console:** All screens share one `Rich Console` for consistent rendering
- **Shared Clients:** HTTP and MQTT clients initialized once, passed to screens
- **Stateless Screens:** Screens don't hold persistent state beyond current data fetch
- **Graceful Shutdown:** Signal handlers ensure clean MQTT/HTTP disconnection

---

## Screen Implementation Patterns

### Standard Screen Template

All SmartNest screens follow this pattern:

```python
class ExampleScreen:
    """Screen description.
    
    Attributes:
        console: Rich Console instance for rendering
        http_client: HTTP client for API requests (optional)
        data: Cached data from last fetch
    """
    
    def __init__(self, console: Console, http_client: httpx.Client | None = None) -> None:
        self.console = console
        self.http_client = http_client
        self.data: list[dict[str, Any]] = []
    
    def fetch_data(self) -> bool:
        """Fetch data from API.
        
        Returns:
            True if successful, False on error
        """
        if not self.http_client:
            return False
        
        try:
            response = self.http_client.get("/api/endpoint")
            response.raise_for_status()
            self.data = response.json().get("data", [])
        except Exception:
            self.data = []
            return False
        else:
            return True
    
    def render(self) -> None:
        """Static render for one-time display."""
        success = self.fetch_data()
        
        self.console.print(self._render_header())
        self.console.print()
        self.console.print(self._render_content(success))
        self.console.print()
        self.console.print(self._render_menu())
    
    def render_live(self) -> Group:
        """Live render for Rich Live updates.
        
        Returns:
            Group of renderables (NOT a list - mypy compatibility)
        """
        success = self.fetch_data()
        
        return Group(
            self._render_header(),
            Text(),  # Blank line
            self._render_content(success),
            Text(),  # Blank line
            self._render_menu(),
        )
    
    def _render_header(self) -> Panel:
        """Render screen header."""
        return Panel(Text("SCREEN TITLE", justify="center", style="bold cyan"))
    
    def _render_content(self, api_success: bool) -> Panel:
        """Render main content area."""
        if not api_success:
            return Panel(Text("API Error", style="bold red"))
        
        table = Table(show_header=True, header_style="bold cyan")
        # Build table from self.data
        return Panel(table, title="[bold yellow]CONTENT[/bold yellow]")
    
    def _render_menu(self) -> Text:
        """Render navigation menu."""
        menu = Text()
        menu.append("[Q]", style="bold blue")
        menu.append(" Quit")
        return menu
```

### Pattern Rules

1. **Constructor:**
   - Accept `Console` (required) and `httpx.Client` (if API needed)
   - Initialize data caches as empty lists/dicts
   - NO API calls in constructor (keep initialization fast)

2. **Data Fetching:**
   - Use `fetch_*()` methods that return `bool` (success/failure)
   - Handle ALL exceptions (network, JSON parsing, timeouts)
   - Return `False` on error, `True` on success
   - Use `try/except/else` pattern with return in `else` block (TRY300 lint compliance)

3. **Rendering:**
   - `render()` for static display (print to console)
   - `render_live()` for live updates (return `Group` object)
   - Private `_render_*()` methods for each UI section
   - Return Rich renderables (`Panel`, `Table`, `Text`, `Group`)

4. **Error Handling:**
   - Never crash on API errors
   - Display user-friendly error panels
   - Log errors using `log_with_code()`

---

## Rich Library Patterns

### Core Components

#### 1. Console

```python
from rich.console import Console

console = Console()
console.print("[bold cyan]Hello SmartNest[/bold cyan]")
console.clear()  # Clear screen
```

**Usage:**
- One console per TUI application (shared across screens)
- Use Rich markup for styling: `[bold cyan]Text[/bold cyan]`
- Auto-detects terminal capabilities (Git Bash, PowerShell, etc.)

#### 2. Panel

```python
from rich.panel import Panel
from rich.text import Text

header = Panel(
    Text("DEVICE LIST", justify="center", style="bold cyan"),
    border_style="dim",
    padding=(0, 0),
    expand=True,
)
```

**Best Practices:**
- Use for section containers (header, content, menu)
- Set `expand=True` for full-width panels
- Use `border_style="dim"` for subtle borders
- Set `title` and `title_align` for labeled sections

#### 3. Table

```python
from rich.table import Table

table = Table(show_header=True, header_style="bold cyan", expand=True)
table.add_column("ID", style="dim", width=10)
table.add_column("Name", style="bold", width=25)
table.add_column("Status", justify="center", width=10)

for device in devices:
    status_text = Text("● ONLINE", style="bold green")
    table.add_row(device["id"], device["name"], status_text)
```

**Best Practices:**
- Set explicit column widths for predictable layout
- Use `justify="center"` or `justify="right"` for numeric columns
- Use `Text` objects for colored status indicators
- Set `expand=True` for full-width tables

#### 4. Text

```python
from rich.text import Text

text = Text()
text.append("[F1]", style="bold blue")
text.append(" Dashboard  ")
text.append("[Q]", style="bold blue")
text.append(" Quit")
```

**Best Practices:**
- Use for multi-styled strings (menus)
- Append segments with different styles
- Avoid Rich markup strings in `.append()` (use `style` parameter)

#### 5. Group

```python
from rich.console import Group

# CORRECT: Individual arguments (mypy compatible)
group = Group(
    panel1,
    Text(),  # Blank line
    panel2,
    Text(),  # Blank line
    panel3,
)

# INCORRECT: Unpacked list (mypy error)
panels = [panel1, Text(), panel2]
group = Group(*panels)  # Type error!
```

**Critical Rule:**
- Pass renderables as **individual arguments**, NOT as unpacked list
- This satisfies mypy's type checking requirements

#### 6. Live

```python
from rich.live import Live

with Live(
    dashboard.render_live(device_count=5, system_status=status),
    console=console,
    refresh_per_second=4,  # 4 FPS = 250ms refresh
    screen=False,           # Don't use alternate screen buffer
) as live:
    while is_running:
        live.update(dashboard.render_live(device_count=count, system_status=status))
        time.sleep(0.25)  # Match refresh rate
```

**Best Practices:**
- Use context manager (`with Live() as live:`)
- Call `live.update()` to refresh display
- Match sleep duration to `refresh_per_second` (4 FPS = 250ms)
- Pass `screen=False` to avoid alternate buffer (keeps history visible)

---

## MQTT Integration

### Subscribing to Topics

```python
# In SmartNestTUI.__init__()
self.mqtt_client = SmartNestMQTTClient(mqtt_config)
self.system_status: dict[str, Any] = {}

# In startup()
self.mqtt_client.connect()
self.mqtt_client.subscribe("smartnest/system/status")
self.mqtt_client.add_topic_handler("smartnest/system/status", self._on_system_status)

# Callback (3-parameter MessageHandler protocol)
def _on_system_status(
    self,
    _client: mqtt.Client,
    _userdata: object,
    message: mqtt.MQTTMessage,
    /,
) -> None:
    """Handle system status messages."""
    try:
        payload = json.loads(message.payload.decode())
        self.system_status = payload
        log_with_code(logger, "debug", MessageCode.TUI_MQTT_MESSAGE_RECEIVED, topic=message.topic)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log_with_code(logger, "warning", MessageCode.TUI_MQTT_MESSAGE_PARSE_ERROR, error=str(e))
```

### MQTT Callback Pattern

**Protocol:** `MessageHandler` (3 parameters)

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import paho.mqtt.client as mqtt

def _on_message(
    self,
    _client: mqtt.Client,      # Paho client instance (unused, prefix with _)
    _userdata: object,          # User data (unused, prefix with _)
    message: mqtt.MQTTMessage,  # MQTT message object
    /,                          # Position-only (protocol requirement)
) -> None:
    """Handle MQTT message."""
    payload = json.loads(message.payload.decode())
    # Process payload
```

**Important Notes:**
- Use 3-parameter signature (`_client`, `_userdata`, `message`)
- Mark as position-only with `/` after parameters
- Import `paho.mqtt.client` only in `TYPE_CHECKING` block (avoid runtime import)
- Prefix unused parameters with `_` (ARG002 lint compliance)

### Integrating MQTT with Live Updates

```python
def run(self) -> None:
    """Main application loop with MQTT live updates."""
    self.startup()  # Connect MQTT
    
    device_count = self._fetch_device_count()
    
    with Live(
        self.dashboard.render_live(device_count=device_count, system_status=self.system_status),
        console=self.console,
        refresh_per_second=4,
    ) as live:
        while self.is_running:
            # Update display with latest MQTT state
            live.update(
                self.dashboard.render_live(
                    device_count=device_count,
                    system_status=self.system_status,  # Updated by MQTT callback
                )
            )
            time.sleep(0.25)  # 4 FPS
```

**Pattern:**
- MQTT callback updates shared state (`self.system_status`)
- Live loop reads state and renders updated UI
- No locking needed (GIL ensures thread safety for dict updates)

---

## HTTP API Integration

### Synchronous HTTP Client

```python
import httpx

http_client = httpx.Client(base_url="http://localhost:8000", timeout=5.0)

# GET request
response = http_client.get("/api/devices")
response.raise_for_status()  # Raises httpx.HTTPStatusError on 4xx/5xx
data = response.json()

# POST request
response = http_client.post(
    "/api/devices/light_01/command",
    json={"command": "set_brightness", "parameters": {"brightness": 75}},
)
response.raise_for_status()
```

**Error Handling Pattern:**

```python
def fetch_devices(self) -> bool:
    """Fetch devices from API."""
    try:
        response = self.http_client.get("/api/devices")
        response.raise_for_status()
        self.devices = response.json().get("devices", [])
    except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException):
        self.devices = []
        return False
    else:
        return True
```

**Best Practices:**
- Use `try/except/else` with return in `else` (TRY300 lint compliance)
- Catch `httpx.HTTPError` base class or specific exceptions
- Always provide fallback values for error cases
- Return boolean success flag for render methods to handle gracefully

---

## Navigation and Keyboard Handling

### Function Key Navigation (Planned)

```python
# In SmartNestTUI.run() - Keyboard event loop (future implementation)
def _handle_key(self, key: str) -> None:
    """Handle keyboard input for navigation."""
    if key == "f1":
        self.current_screen = "dashboard"
    elif key == "f2":
        self.current_screen = "settings"
    elif key == "f3":
        self.current_screen = "device_list"
    elif key == "f4":
        self.current_screen = "sensor_view"
    elif key.lower() == "q":
        self.shutdown()
```

**Current Implementation:**
- Dashboard runs in live mode (no keyboard handling yet)
- Future: Add `prompt-toolkit` for keyboard input
- Function keys (F1-F4) for screen navigation
- Letter keys for screen-specific actions

### Screen-Specific Actions

**Device List Screen:**
- `L` - Filter by lights
- `S` - Filter by sensors
- `W` - Filter by switches
- `A` - Show all devices
- `/` - Search prompt
- `Enter` - Open device detail

**Device Detail Screen (Smart Lights):**
- `P` - Toggle power
- `+/-` - Brightness adjustment (±10%)
- `↑/↓` - Color temperature (±500K)
- `Esc` - Back to device list

**Sensor View Screen:**
- `R` - Refresh data
- `E` - Export to CSV (future)

---

## Testing Strategies

### Unit Testing Pattern

**Goal:** Test screen logic in isolation, mock external dependencies

#### Testing Screen Initialization

```python
import pytest
from unittest.mock import MagicMock
from rich.console import Console
import httpx

@pytest.fixture
def mock_console() -> MagicMock:
    """Create mock Console for testing."""
    return MagicMock(spec=Console)

@pytest.fixture
def mock_http_client() -> MagicMock:
    """Create mock HTTP client for testing."""
    return MagicMock(spec=httpx.Client)

def test_screen_initialization(mock_console: MagicMock, mock_http_client: MagicMock):
    """Test that screen initializes with correct dependencies."""
    screen = ExampleScreen(mock_console, mock_http_client)
    assert screen.console is mock_console
    assert screen.http_client is mock_http_client
    assert screen.data == []
```

#### Testing API Fetching

```python
def test_fetch_data_success(screen: ExampleScreen, mock_http_client: MagicMock):
    """Test successful data fetch from API."""
    # Mock API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"id": 1, "name": "Device 1"}]
    }
    mock_http_client.get.return_value = mock_response
    
    # Fetch data
    success = screen.fetch_data()
    
    # Assert
    assert success is True
    assert len(screen.data) == 1
    assert screen.data[0]["name"] == "Device 1"
    mock_http_client.get.assert_called_once_with("/api/endpoint")

def test_fetch_data_error(screen: ExampleScreen, mock_http_client: MagicMock):
    """Test API error handling."""
    # Mock API error
    mock_http_client.get.side_effect = httpx.RequestError("Connection error", request=MagicMock())
    
    # Fetch data
    success = screen.fetch_data()
    
    # Assert
    assert success is False
    assert screen.data == []
```

#### Testing Rendering Methods

```python
def test_render_header(screen: ExampleScreen):
    """Test _render_header returns Panel."""
    header = screen._render_header()
    assert isinstance(header, Panel)

def test_render_content_success(screen: ExampleScreen):
    """Test _render_content with successful data."""
    screen.data = [{"id": 1, "name": "Device 1"}]
    content = screen._render_content(api_success=True)
    assert isinstance(content, Panel)

def test_render_content_error(screen: ExampleScreen):
    """Test _render_content with API error."""
    content = screen._render_content(api_success=False)
    assert isinstance(content, Panel)
```

#### Testing render_live()

```python
def test_render_live_fetches_data(screen: ExampleScreen, mock_http_client: MagicMock):
    """Test render_live fetches data and returns Group."""
    # Mock API response
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}
    mock_http_client.get.return_value = mock_response
    
    # Render live
    result = screen.render_live()
    
    # Assert
    assert isinstance(result, Group)
    mock_http_client.get.assert_called_once()

def test_render_live_handles_error(screen: ExampleScreen, mock_http_client: MagicMock):
    """Test render_live handles API error gracefully."""
    mock_http_client.get.side_effect = httpx.RequestError("Connection error", request=MagicMock())
    
    # Render live
    result = screen.render_live()
    
    # Assert - Should still return Group (error panel inside)
    assert isinstance(result, Group)
```

#### Testing render()

```python
def test_render_calls_methods(screen: ExampleScreen, mock_console: MagicMock, mock_http_client: MagicMock):
    """Test render method calls all rendering methods."""
    # Mock API response
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}
    mock_http_client.get.return_value = mock_response
    
    # Render
    screen.render()
    
    # Assert console.print was called (5+ times for typical screen)
    assert mock_console.print.call_count >= 5
```

### Coverage Strategies

#### Branch Coverage Checklist

For each conditional in screen code, ensure tests cover:

- ✅ `if status == "online"` → Test online status
- ✅ `elif status == "offline"` → Test offline status
- ✅ `else` → Test unknown status

- ✅ `if api_success` → Test with `api_success=True`
- ✅ `else` → Test with `api_success=False`

- ✅ `if device.get("device_type") == "smart_light"` → Test smart_light
- ✅ `else` → Test non-light device (temperature_sensor)

- ✅ `if brightness is not None` → Test with brightness present
- ✅ Implicit else → Test without brightness (not in dict)

#### Example: Testing All Status Branches

```python
def test_render_online_status(screen: ExampleScreen):
    screen.device = {"status": "online"}
    panel = screen._render_device_info(api_success=True)
    assert isinstance(panel, Panel)

def test_render_offline_status(screen: ExampleScreen):
    screen.device = {"status": "offline"}
    panel = screen._render_device_info(api_success=True)
    assert isinstance(panel, Panel)

def test_render_unknown_status(screen: ExampleScreen):
    screen.device = {"status": "unknown"}
    panel = screen._render_device_info(api_success=True)
    assert isinstance(panel, Panel)
```

### Testing MQTT Integration

#### Testing TUI MQTT Callbacks

```python
import json
from unittest.mock import MagicMock, patch

def test_on_system_status_updates_state():
    """Test MQTT callback updates system_status dict."""
    tui = SmartNestTUI()
    
    # Mock MQTT message
    mock_message = MagicMock()
    mock_message.topic = "smartnest/system/status"
    mock_message.payload = json.dumps({"mqtt_status": "online"}).encode()
    
    # Call callback
    tui._on_system_status(MagicMock(), None, mock_message)
    
    # Assert state updated
    assert tui.system_status["mqtt_status"] == "online"

def test_on_system_status_handles_invalid_json():
    """Test MQTT callback handles parse errors."""
    tui = SmartNestTUI()
    
    # Mock invalid message
    mock_message = MagicMock()
    mock_message.payload = b"invalid json"
    
    # Call callback (should not raise)
    tui._on_system_status(MagicMock(), None, mock_message)
    
    # Assert state unchanged
    assert tui.system_status == {}
```

#### Testing MQTT Connection Lifecycle

```python
def test_startup_connects_mqtt():
    """Test startup() connects MQTT and subscribes."""
    tui = SmartNestTUI()
    
    with patch.object(tui.mqtt_client, "connect") as mock_connect, \
         patch.object(tui.mqtt_client, "subscribe") as mock_subscribe, \
         patch.object(tui.mqtt_client, "add_topic_handler") as mock_handler:
        
        tui.startup()
        
        mock_connect.assert_called_once()
        mock_subscribe.assert_called_once_with("smartnest/system/status")
        mock_handler.assert_called_once()

def test_shutdown_disconnects_mqtt():
    """Test shutdown() disconnects MQTT."""
    tui = SmartNestTUI()
    tui.is_running = True
    
    with patch.object(tui.mqtt_client, "disconnect") as mock_disconnect:
        tui.shutdown()
        mock_disconnect.assert_called_once()
```

---

## Performance Optimization

### Rendering Performance

**Problem:** Rich Live updates every 250ms, re-rendering entire screen

**Solutions:**
1. **Efficient Data Structures:** Cache API responses, only fetch when needed
2. **Minimal Rendering:** Only render visible data (paginate large tables)
3. **Lazy Fetching:** Defer expensive API calls until screen is displayed

**Example: Conditional Fetching**

```python
def render_live(self) -> Group:
    """Only fetch data if screen is active."""
    if self.tui.current_screen == "device_list":  # Future: Pass active screen flag
        success = self.fetch_devices()
    else:
        success = True  # Use cached data
    
    return Group(self._render_table(success), ...)
```

### HTTP Client Reuse

**Problem:** Creating new `httpx.Client` per request is expensive

**Solution:** Share single client across all screens

```python
# GOOD: One client, passed to all screens
self.http_client = httpx.Client(base_url=api_base_url, timeout=5.0)
self.device_list = DeviceListScreen(self.console, self.http_client)
self.settings = SettingsScreen(self.console, self.http_client)

# BAD: Each screen creates own client
class DeviceListScreen:
    def __init__(self, console: Console):
        self.http_client = httpx.Client()  # New client per screen!
```

### MQTT Connection Reuse

**Problem:** Multiple MQTT connections drain resources

**Solution:** Single `SmartNestMQTTClient` shared by TUI application

```python
# GOOD: One MQTT client for entire TUI
self.mqtt_client = SmartNestMQTTClient(mqtt_config)
self.mqtt_client.subscribe("smartnest/system/status")
self.mqtt_client.subscribe("smartnest/device/+/state")  # Wildcard subscription

# BAD: Each screen creates own MQTT client
```

---

## Common Patterns and Idioms

### Pattern 1: Error-Resilient Rendering

```python
def _render_content(self, api_success: bool) -> Panel:
    """Render content with graceful API error handling."""
    if not api_success:
        return Panel(
            Text("API Error: Unable to fetch data", style="bold red"),
            title="[bold yellow]ERROR[/bold yellow]",
            border_style="red",
        )
    
    # Normal rendering
    table = Table(...)
    return Panel(table, title="[bold yellow]DATA[/bold yellow]")
```

### Pattern 2: Status Color Coding

```python
def _render_status(self, status: str) -> Text:
    """Render status with color coding."""
    if status == "online":
        return Text("● ONLINE", style="bold green")
    elif status == "offline":
        return Text("● OFFLINE", style="bold red")
    else:
        return Text("● UNKNOWN", style="bold yellow")
```

### Pattern 3: Ternary Operators for Simple Conditionals

```python
# GOOD: Use ternary for simple value selection
last_seen_display = str(last_seen)[11:19] if last_seen else "Never"

# BAD: Verbose if-else (SIM108 lint error)
if last_seen:
    last_seen_display = str(last_seen)[11:19]
else:
    last_seen_display = "Never"
```

### Pattern 4: Progress Bars

```python
def _render_progress_bar(self, value: int, max_value: int, width: int = 30) -> Text:
    """Render ASCII progress bar."""
    filled = int((value / max_value) * width)
    bar = Text()
    bar.append("█" * filled, style="bold cyan")
    bar.append("░" * (width - filled), style="dim")
    bar.append(f" {value}%", style="bold")
    return bar

# Usage in table
table.add_row("Brightness:", self._render_progress_bar(75, 100))
```

---

## Debugging Tips

### 1. Rich Console Logging

```python
from rich.console import Console

console = Console()
console.log("[DEBUG] Device data:", devices)  # Syntax-highlighted output
console.print_exception()  # Pretty exception formatting
```

### 2. Inspecting Mock Calls

```python
# Check if mock was called
assert mock_http_client.get.called

# Check call count
assert mock_http_client.get.call_count == 2

# Check call arguments
mock_http_client.get.assert_called_with("/api/devices")
mock_http_client.get.assert_called_once_with("/api/devices")

# Inspect all calls
print(mock_http_client.get.call_args_list)
```

### 3. Debugging Live Updates

```python
with Live(..., console=console, screen=False) as live:
    console.log("[DEBUG] System status:", self.system_status)  # Visible during live updates
    live.update(self.dashboard.render_live(...))
```

### 4. MQTT Message Debugging

```python
def _on_system_status(self, _client, _userdata, message, /):
    """Debug MQTT messages."""
    print(f"[DEBUG] Topic: {message.topic}")
    print(f"[DEBUG] Payload: {message.payload.decode()}")
    
    payload = json.loads(message.payload.decode())
    self.system_status = payload
```

---

## Best Practices Summary

### Do's

- ✅ Share Console, HTTP, and MQTT clients across screens
- ✅ Use `try/except/else` with return in `else` block
- ✅ Return `bool` from fetch methods for error handling
- ✅ Use `Group` with individual arguments (not unpacked list)
- ✅ Handle API errors gracefully (render error panels)
- ✅ Use ternary operators for simple conditionals
- ✅ Test all branches (online/offline/unknown)
- ✅ Mock external dependencies in unit tests
- ✅ Use `TYPE_CHECKING` for `paho.mqtt.client` imports
- ✅ Prefix unused callback params with `_`

### Don'ts

- ❌ Don't create clients inside screen constructors
- ❌ Don't make API calls during initialization
- ❌ Don't use `Group(*list)` (mypy error)
- ❌ Don't use `if-else` blocks for simple value selection (SIM108)
- ❌ Don't ignore API errors (always provide fallback)
- ❌ Don't skip branch coverage tests
- ❌ Don't import `paho.mqtt.client` at runtime (TC002)
- ❌ Don't use 4-parameter MQTT callbacks (deprecated)

---

## Extending the TUI

### Adding a New Screen

1. **Create Screen File:** `backend/tui/screens/new_screen.py`

```python
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
import httpx

class NewScreen:
    def __init__(self, console: Console, http_client: httpx.Client):
        self.console = console
        self.http_client = http_client
    
    def render_live(self) -> Group:
        return Group(
            Panel(Text("New Screen", style="bold cyan")),
        )
```

2. **Export Screen:** Add to `backend/tui/screens/__init__.py`

```python
from backend.tui.screens.new_screen import NewScreen

__all__ = [..., "NewScreen"]
```

3. **Initialize in TUI:** Add to `SmartNestTUI.__init__()` in `backend/tui/app.py`

```python
self.new_screen = NewScreen(self.console, self.http_client)
```

4. **Add Navigation:** Implement keyboard handler (future)

5. **Create Tests:** `tests/unit/tui/test_new_screen.py`

---

## References

- [SmartNest Architecture Overview](architecture.md) - Full system architecture
- [Rich Documentation](https://rich.readthedocs.io/) - Official Rich library docs
- [httpx Documentation](https://www.python-httpx.org/) - HTTP client usage
- [Paho MQTT Python](https://eclipse.dev/paho/files/paho.mqtt.python/html/index.html) - MQTT client API

---

**Project:** SmartNest Home Automation Management System  
**Developer:** Krystian Spiewak  
**Course:** SDEV435 - Capstone Project  
**Institution:** Champlain College
