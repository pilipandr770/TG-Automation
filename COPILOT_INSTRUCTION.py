"""
GITHUB COPILOT INSTRUCTION TEMPLATE
=====================================

Copy and paste this entire prompt into GitHub Copilot Chat to guide
the refactoring of your Telegram automation project to use centralized
dispatching instead of direct client instantiation.

This will help Copilot understand:
1. Current architectural issues
2. Desired final state
3. Step-by-step migration approach
4. Files to modify and how
5. Testing strategy

---
"""

COPILOT_INSTRUCTION = '''
# 🎯 TELEGRAM AUTOMATION REFACTORING INSTRUCTION FOR GITHUB COPILOT

## CONTEXT

I have a Flask + Telethon Telegram automation project with the following structure:

```
app/
  __init__.py                   # Flask app initialization
  routes/
    admin_routes.py             # Web admin interface (1234 lines)
    api_routes.py               # API endpoints
    auth_routes.py              # Authentication
  services/
    telegram_client.py          # TelegramClientManager singleton (238 lines)
    discovery_service.py        # Channel discovery (790 lines)
    audience_service.py         # Audience analysis
    publisher_service.py        # Post publishing
    invitation_service.py       # User invitations
    conversation_service.py     # Conversation handling
    coordinator_service.py      # Round-robin orchestration (238 lines)
    telegram_dispatcher.py      # NEW: Async queue orchestrator (260 lines)
    dispatcher_integration_guide.py  # Integration examples
  models.py                     # SQLAlchemy models
  enums.py                      # Enums
telethon_runner.py              # Main async event loop (347 lines)
run.py                          # Flask + Telethon coordination (294 lines)
worker.py                       # Background worker (unknown)
requirements.txt                # Dependencies (includes telethon, flask, sqlalchemy)
config.py                       # Configuration
```

## ⚠️ PROBLEM DIAGNOSED

**Root Issue**: Multiple potential TelegramClient instances competing for resources.

**Current Findings**:
- ✅ app/services/telegram_client.py: Singleton TelegramClientManager exists
- ✅ telethon_runner.py: Correctly uses TelegramClientManager singleton
- ✅ Services (discovery, audience, etc.): Properly receive client_manager in constructor
- ❌ app/routes/admin_routes.py line ~249: **Creates separate TelegramClient directly**
  - `from telethon import TelegramClient`
  - `client = TelegramClient(session, api_id, api_hash)  # ❌ PROBLEM`
- ❓ worker.py: Unknown - may also create clients
- ❓ scripts/ directory: Unknown - may create clients in standalone scripts

**Consequences**:
- Session file locks (SQLite serialization)
- MTProto connection conflicts
- Flood limit state not shared
- Unpredictable behavior when modules run together
- Service crashes due to state inconsistency

## ✅ SOLUTION IMPLEMENTED

**File Created**: app/services/telegram_dispatcher.py (260 lines)

```python
class TaskType(Enum):
    SEARCH = "search"
    JOIN = "join"
    PARSE = "parse"
    INVITE = "invite"
    POST = "post"
    REPLY = "reply"
    CUSTOM = "custom"

@dataclass
class TelegramTask:
    task_type: TaskType
    operation: Callable  # The actual async method
    args: tuple = ()
    kwargs: dict = None
    timeout: float = 30.0

class TelegramDispatcher:
    async def start():      # Start background worker
    async def stop():       # Graceful shutdown
    async def submit(task): # Queue task, wait for result
    get_stats():            # Return execution metrics
```

This creates a **single asyncio.Queue** where all Telegram operations are submitted
and executed **sequentially** (one at a time) to prevent conflicts.

## 🎯 DESIRED FINAL STATE

### Architecture:
- ✅ ONE TelegramClient instance (singleton)
- ✅ ONE TelegramDispatcher instance (singleton)
- ✅ ALL Telegram API calls go through dispatcher
- ✅ ALL services receive dispatcher, not client directly
- ✅ NO direct `TelegramClient(...)` creation anywhere
- ✅ NO `time.sleep()` in async code (use `await asyncio.sleep()`)

### Code Changes Needed:

**1. admin_routes.py (Priority: CRITICAL)**
   - REMOVE: Direct `from telethon import TelegramClient` import
   - REMOVE: Lines ~249 that create `TelegramClient(session, ...)`
   - ADD: Import dispatcher: `from app.services.telegram_dispatcher import get_telegram_dispatcher`
   - REPLACE: Session management operations with dispatcher tasks
   - RESULT: No direct client usage in web routes

**2. telethon_runner.py (Priority: HIGH)**
   - ADD: Initialize dispatcher in main()
   - ADD: `await dispatcher.start()` before coordinator loop
   - ADD: `await dispatcher.stop()` in shutdown handler
   - UPDATE: Pass dispatcher to services (already have client_manager)
   - RESULT: Dispatcher is active during background worker operation

**3. Each service: discovery, audience, publisher, invitation (Priority: HIGH)**
   - ADD: `self._dispatcher = None` in __init__
   - ADD: Helper method `async def _get_dispatcher()`
   - ADD: Helper method `async def _dispatch_telegram_op(...)`
   - REPLACE: Direct client calls:
     ```
     # OLD: client = await self._client_manager.get_client()
     #      result = await client.search_global(keyword)
     
     # NEW: result = await self._dispatch_telegram_op(
     #          TaskType.SEARCH,
     #          self._search_impl,  # Your internal method
     #          keyword
     #      )
     ```
   - RESULT: All Telegram operations flow through dispatcher

**4. coordinator_service.py (Priority: MEDIUM)**
   - No changes needed - it orchestrates services, not direct client
   - Services now use dispatcher internally

**5. Find and remove blocking calls (Priority: MEDIUM)**
   - Search: `import time` and `time.sleep()`
   - Search: `import threading` mixed with `async` code
   - Replace: `time.sleep(N)` → `await asyncio.sleep(N)`
   - Verify: No synchronous I/O in async methods

## 📋 STEP-BY-STEP MIGRATION GUIDE

### Phase 1: Pre-Migration (Complete - Done)
- ✅ Create TelegramDispatcher class (telegram_dispatcher.py - 260 lines)
- ✅ Create integration guide (dispatcher_integration_guide.py)
- ✅ Audit for all TelegramClient instantiation points

### Phase 2: Core Service Updates (Next)

**Step A: Update discovery_service.py**
- Current state: Properly receives client_manager
- Changes needed:
  1. Add to __init__: `self._dispatcher = None`
  2. Add method: `async def _get_dispatcher()`
  3. Add method: `async def _dispatch_telegram_op(...)`
  4. Find all `await self._client_manager.get_client()` calls
  5. Replace with dispatcher submissions
  6. Ensure operations are wrapped in executable methods
- Expected result: All Telegram APIs go through dispatcher

**Step B: Update audience_service.py** (same pattern as Step A)
**Step C: Update publisher_service.py** (same pattern as Step A)
**Step D: Update invitation_service.py** (same pattern as Step A)
**Step E: Update conversation_service.py** (special handling for event handlers)

### Phase 3: Web Routes Refactoring (Critical)

**Step F: Fix admin_routes.py (HIGHEST PRIORITY)**
- Line ~219: Remove `from telethon import TelegramClient`
- Line ~249: Remove the direct client creation
- Add: `from app.services.telegram_dispatcher import get_telegram_dispatcher`
- Scenario: Session management route (GET /telegram-session)
  - Current: Creates client directly to manage session
  - New: Uses dispatcher for session operations
  - Implementation:
    ```python
    dispatcher = await get_telegram_dispatcher()
    task = TelegramTask(
        task_type=TaskType.CUSTOM,
        operation=_load_session_impl,
        timeout=10.0
    )
    result = await dispatcher.submit(task)
    ```

**Step G: Check other routes for client usage**
- Search admin_routes.py for all client method calls
- Convert to dispatcher pattern

### Phase 4: Main Event Loop Integration

**Step H: Update telethon_runner.py**
- Location: `async def main()`
- Before: Initialize services
- Add:
  ```python
  dispatcher = await get_telegram_dispatcher()
  await dispatcher.start()
  logger.info('✅ TelegramDispatcher started')
  ```
- After: Start coordinator
- On shutdown:
  ```python
  await dispatcher.stop()
  stats = dispatcher.get_stats()
  logger.info(f'📊 Dispatcher stats: {stats}')
  ```

### Phase 5: Code Cleanup

**Step I: Remove blocking calls**
- Search workspace: `time.sleep\(`
- Replace with: `await asyncio.sleep(...)`
- Verify: No threading in async contexts

**Step J: Verify no duplicate client creation**
- Search: `TelegramClient\(\|from telethon import TelegramClient`
- Should only find:
  - telegram_client.py (singleton creation)
  - admin_routes.py (updated to remove)
  - Imports in proper locations

### Phase 6: Testing & Validation

**Step K: Integration testing**
- Run: `python telethon_runner.py`
- Expected: Dispatcher initializes, logs [DISPATCH] messages
- Monitor: No more TelegramClient conflicts
- Verify: Services work normally

**Step L: End-to-end testing**
- Test discovery service: Search channels
- Test audience service: Parse members
- Test publisher service: Post message
- Test invitation service: Invite users
- All should log through dispatcher

## 🔍 SPECIFIC CODE PATTERNS TO USE

### Pattern 1: Simple Dispatcher Submission
```python
async def search_channels(self, keyword: str):
    dispatcher = await self._get_dispatcher()
    task = TelegramTask(
        task_type=TaskType.SEARCH,
        operation=self._search_impl,
        args=(keyword,),
        timeout=30.0
    )
    result = await dispatcher.submit(task)
    return result.data if result.success else None

async def _search_impl(self, keyword: str):
    # This is the actual operation that will be submitted
    client = await self._client_manager.get_client()
    return await client.get_dialogs()
```

### Pattern 2: Dispatcher with Error Handling
```python
async def join_channels(self, channel_ids: list):
    dispatcher = await self._get_dispatcher()
    results = []
    
    for channel_id in channel_ids:
        task = TelegramTask(
            task_type=TaskType.JOIN,
            operation=self._join_impl,
            args=(channel_id,),
            timeout=15.0
        )
        result = await dispatcher.submit(task)
        
        if result.success:
            results.append(channel_id)
            logger.info(f'✅ Joined {channel_id}')
        else:
            logger.error(f'❌ Failed to join {channel_id}: {result.error}')
    
    return results
```

### Pattern 3: Coordinator Integration
```python
# In telethon_runner.py main()
async def main():
    app = create_app()
    
    # Initialize dispatcher
    dispatcher = await get_telegram_dispatcher()
    await dispatcher.start()
    logger.info('✅ Dispatcher ready')
    
    # Initialize services
    client_mgr = get_telegram_client_manager()
    discovery = DiscoveryService(client_mgr)
    audience = AudienceService(client_mgr)
    
    # Run coordinator
    coordinator = CoordinatorService(...)
    
    try:
        await coordinator.run()
    finally:
        await dispatcher.stop()
        stats = dispatcher.get_stats()
        logger.info(f'Stats: {stats}')
```

## ✅ VALIDATION CHECKLIST

After each step, verify:
- [ ] File compiles (no syntax errors)
- [ ] All imports resolve (no ImportError)
- [ ] Service initializes (no initialization errors)
- [ ] Logs show expected messages
- [ ] No direct TelegramClient(...) creation in modified files
- [ ] All dispatcher.submit() calls have proper error handling

## 📊 SUCCESS CRITERIA

You'll know the refactoring is complete when:
1. ✅ No direct `TelegramClient(...)` instantiation anywhere except telegram_client.py
2. ✅ all services accept dispatcher in constructor
3. ✅ telethon_runner.py initializes dispatcher and passes to services
4. ✅ Services submit all Telegram operations through dispatcher
5. ✅ No `time.sleep()` in async code
6. ✅ Logs show [DISPATCH] messages (task submitted, queued, executed)
7. ✅ Services work correctly in coordinator loop without conflicts
8. ✅ Multiple concurrent coordinator cycles don't cause crashes

## 🎓 WHY THIS PATTERN?

- **asyncio.Queue**: Serializes operations, prevents concurrency issues
- **TaskType Enum**: Categorizes operations for metrics/logging
- **TelegramTask dataclass**: Encapsulates operation + args + timeout
- **TaskResult dataclass**: Consistent error/success handling
- **Single dispatcher instance**: One point of control for all Telegram API calls
- **Timeout per task**: Prevents deadlocks, handles slow operations
- **Metrics**: Track success rate, identify problematic operations

## ⚠️ CRITICAL NOTES

1. **NEVER** create TelegramClient directly outside telegram_client.py
2. **ALWAYS** submit Telegram operations through dispatcher
3. **ALWAYS** use `await asyncio.sleep()` instead of `time.sleep()` in async code
4. **ALWAYS** handle TaskResult.success flag (not just TaskResult.data)
5. **ALWAYS** set appropriate timeout for long operations
6. **ALWAYS** log operation start/completion for debugging
7. Services should have ZERO knowledge of each other - only dispatcher
8. Blocking calls will crash the async loop - search and replace ALL

## 📝 EXPECTED TASK SIZE

- admin_routes.py: ~100 lines changed (remove client creation, add dispatcher calls)
- discovery_service.py: ~200 lines changed (add dispatcher wrapper, update calls)
- audience_service.py: ~200 lines changed (same pattern)
- publisher_service.py: ~150 lines changed (same pattern)
- invitation_service.py: ~150 lines changed (same pattern)
- conversation_service.py: ~50 lines changed (event handlers special case)
- telethon_runner.py: ~20 lines added (dispatcher init/shutdown)
- coordinator_service.py: No changes needed

**TOTAL: ~870 lines of refactoring across 7 files**

## 🚀 EXECUTION STRATEGY

This refactoring can be done:
1. **Incrementally**: Fix one file at a time, test each
2. **Parallel**: Update all services in parallel structure
3. **Service-by-service**: Fix each service, verify with unit tests

Recommended: **Fix admin_routes.py first** (highest impact), then all services in parallel.

---

Now please:

1. **FIRST**: Review the current admin_routes.py to identify exact line numbers with direct
   client creation and session management logic.

2. **THEN**: Show me the changes needed for admin_routes.py to use dispatcher instead of
   direct TelegramClient.

3. **NEXT**: Provide a refactored version of one service (e.g., discovery_service.py) using
   the dispatcher pattern.

4. **FINALLY**: Create updated telethon_runner.py showing dispatcher initialization and
   integration with coordinator.

For each code change, please:
- Show the OLD code that needs to be changed
- Show the NEW code with dispatcher pattern
- Explain why this change is necessary
- Note any edge cases or special handling

Keep the business logic EXACTLY THE SAME - we''re only changing HOW the Telegram client
is accessed, not WHAT operations are performed.
'''

print(COPILOT_INSTRUCTION)
