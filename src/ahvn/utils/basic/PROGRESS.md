# Progress Utils

A unified, thread-safe progress reporting system supporting multiple backends.

<br/>

## 1. Quick Start

```python
from ahvn.utils.basic import Progress, NoProgress, LogProgress, TqdmProgress, progress, get_progress

# 1.1 Direct usage with tqdm
with TqdmProgress(total=100, desc="Processing") as pbar:
    for i in range(100):
        pbar.update(1)

# 1.2 Context-based usage (for deep call stacks)
with progress(TqdmProgress(total=100, desc="Processing")):
    result = some_deep_function()  # can call get_progress() internally

# 1.3 Silent mode (default)
pbar = get_progress()  # Returns NoProgress if no context is active
pbar.update(1)         # Does nothing silently
```

<br/>

## 2. Built-in Progress Classes

### 2.1 `NoProgress` (Default)

Silent implementation that does nothing. Used when no progress bar is needed.

```python
pbar = NoProgress(total=100)
pbar.update(1)  # Silent
```

### 2.2 `TqdmProgress`

Terminal-based progress bar using tqdm.

```python
with TqdmProgress(total=100, desc="Loading", unit="files") as pbar:
    for i in range(100):
        pbar.set_postfix(file=f"data_{i}.json")
        pbar.update(1)
# Output: Loading: 100%|████████████| 100/100 [00:10<00:00, file=data_99.json]
```

### 2.3 `LogProgress`

Logger-based progress for server/backend environments.

```python
from ahvn.utils.basic import get_logger
logger = get_logger("myapp")

with LogProgress(total=100, desc="Processing", logger=logger, interval=25) as pbar:
    for i in range(100):
        pbar.update(1)
# Output:
# [INFO] Processing: [0%]
# [INFO] Processing: [25%]
# [INFO] Processing: [50%]
# [INFO] Processing: [75%]
# [INFO] Processing: [100%]
```

<br/>

## 3. Context-Based Usage

Use `progress()` context manager to set active progress for deep call stacks.

```python
from ahvn.utils.basic import progress, get_progress, TqdmProgress

def deep_function():
    pbar = get_progress()  # Gets active progress or NoProgress
    pbar.update(1)

def middle_function():
    deep_function()

def main():
    with progress(TqdmProgress(total=10, desc="Main")) as pbar:
        for i in range(10):
            middle_function()  # deep_function() will update the progress

main()
```

### 3.1 Nested Progress

```python
with progress(TqdmProgress(total=3, desc="Outer")) as outer:
    for i in range(3):
        with progress(TqdmProgress(total=5, desc="Inner")) as inner:
            for j in range(5):
                inner.update(1)
        outer.update(1)
```

<br/>

## 4. With Parallelized

```python
from ahvn.utils.basic import Parallelized, TqdmProgress, LogProgress, NoProgress

# Default: TqdmProgress
with Parallelized(my_func, args, desc="Tasks") as tasks:
    for kwargs, result, error in tasks:
        pass

# Use LogProgress for servers
with Parallelized(my_func, args, desc="Tasks", progress=LogProgress) as tasks:
    for kwargs, result, error in tasks:
        pass

# Silent mode
with Parallelized(my_func, args, progress=NoProgress) as tasks:
    for kwargs, result, error in tasks:
        pass
```

<br/>

## 5. With KLEngine/KLBase Sync

```python
from ahvn.klengine import BaseKLEngine
from ahvn.klbase import KLBase
from ahvn.utils.basic import TqdmProgress, LogProgress

# Sync a single engine with tqdm progress
engine.sync(progress=TqdmProgress)

# Sync a single engine with log progress (for servers)
engine.sync(progress=LogProgress)

# Sync all engines in a KLBase
klbase.sync(progress=TqdmProgress)

# Silent sync (default)
klbase.sync()
```

### 5.1 Batch Operations

- `batch_upsert`, `batch_insert`, and `batch_remove` on KLStore/KLEngine/KLBase now accept `progress: Type[Progress]`.
- Progress totals use item counts; updates advance by the batch size (length of each batch) rather than batch count.

```python
# KLStore batch upsert with item-count progress
store.batch_upsert(kls, progress=TqdmProgress)

# KLBase aggregates totals across storages/engines
klbase.batch_upsert(kls, progress=LogProgress)
```

<br/>

## 6. Custom Progress (Frontend Integration)

Inherit from `Progress` to create custom implementations.

### 6.1 WebSocket Progress (Example)

```python
from ahvn.utils.basic import Progress

class WebSocketProgress(Progress):
    """Send progress updates via WebSocket."""
    
    def __init__(self, websocket, total=None, desc=None, **kwargs):
        super().__init__(total=total, desc=desc, **kwargs)
        self.ws = websocket
    
    def _send(self):
        self.ws.send_json({
            "type": "progress",
            "n": self._n,
            "total": self._total,
            "desc": self._desc,
            "percent": int(100 * self._n / self._total) if self._total else None,
        })
    
    def update(self, n=1):
        self._n += n
        self._send()
    
    def set_description(self, desc=None, refresh=True):
        self._desc = desc
        if refresh:
            self._send()
    
    def set_postfix(self, ordered_dict=None, refresh=True, **kwargs):
        pass  # Or send postfix data
    
    def write(self, s, file=None, end="\n"):
        self.ws.send_json({"type": "log", "message": s})
    
    def close(self):
        if not self._closed:
            self._send()
            self._closed = True
```

### 6.2 Using Custom Progress

```python
# Direct usage
with WebSocketProgress(ws, total=100, desc="Processing") as pbar:
    for i in range(100):
        pbar.update(1)

# Context-based (for library functions)
with progress(WebSocketProgress(ws, total=100)):
    result = library_function()  # Calls get_progress() internally

# With Parallelized
with Parallelized(func, args, progress=lambda **kw: WebSocketProgress(ws, **kw)) as tasks:
    for kwargs, result, error in tasks:
        pass
```

<br/>

## 7. API Reference

### 7.1 `Progress` (Abstract Base Class)

| Property/Method | Description |
|----------------|-------------|
| `total` | Get/set total iterations |
| `n` | Current iteration count (read-only) |
| `desc` | Description (read-only) |
| `update(n=1)` | Advance progress by n steps |
| `update_total(total)` | Change total iterations |
| `emit(payload)` | Handle standardized payload keys (`total`, `update`/`advance`, optional `refresh`) |
| `close()` | Cleanup and close |
| `reset(total=None)` | Reset to initial state |
| `set_description(desc, refresh=True)` | Optional helper to set description |
| `set_postfix(dict, refresh=True, **kw)` | Optional helper to set suffix |
| `write(s, file=None, end="\n")` | Optional helper to write log-like messages |

**Emit payloads**

- `total`: update total iterations.
- `update` / `advance`: advance by the given amount (int).
- `refresh`: optional bool forwarded to subclasses that need a repaint hint.
- Additional keys are subclass-specific (e.g., `description`, `postfix`, `message`).

### 7.2 `LogProgress` Extra

| Parameter | Default | Description |
|-----------|---------|-------------|
| `logger` | root | Logger instance to use |
| `level` | INFO | Log level |
| `interval` | 10 | Log every N percent change |

### 7.3 Context Functions

| Function | Description |
|----------|-------------|
| `progress(p)` | Context manager to set active progress |
| `get_progress()` | Get active progress (or NoProgress) |
