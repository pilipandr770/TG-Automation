"""
QUICK START: Using GitHub Copilot to Fix Telegram Orchestration

This is a practical step-by-step guide to use GitHub Copilot effectively
to refactor your project from multiple TelegramClient instances to a
centralized TelegramDispatcher.
"""

QUICK_START = '''
╔════════════════════════════════════════════════════════════════════════════╗
║         TELEGRAM AUTOMATION: ORCHESTRATION FIX WITH GITHUB COPILOT        ║
║                         QUICK START GUIDE                                  ║
╚════════════════════════════════════════════════════════════════════════════╝


🎯 WHAT YOU'LL DO
─────────────────

Transform your project from this (BROKEN):
    Route 1 → TelegramClient #1 ──┐
    Route 2 → TelegramClient #2 ──┼─→ SESSION FILE (LOCK CONFLICTS!)
    Service  → TelegramClient #3 ──┘

To this (FIXED):
    Route 1 ──┐
    Route 2 ──┼─→ TelegramDispatcher (asyncio.Queue) → TelegramClient (SINGLETON)
    Service ──┘


⏱️ ESTIMATED TIME
─────────────────

If you follow this guide exactly:
- Easy routes (2-3 hours): admin_routes.py + 1 service
- Full project (5-7 hours): all routes + all services
- Testing (1-2 hours): manual testing + verification

Total: 8-11 hours for complete refactoring


📝 PREREQUISITES
────────────────

✅ telegram_dispatcher.py created (260 lines) - DONE
✅ dispatcher_integration_guide.py created - DONE
✅ COPILOT_INSTRUCTION.py created - DONE
✅ ADMIN_ROUTES_REFACTORING.py created - DONE
✅ telethon_runner.py running (you can test at end)
✅ All services initialized


🚀 EXECUTION PLAN
─────────────────

PHASE 1: Prepare (15 minutes)
──────────────────────────────
1. Open GitHub Copilot Chat (Ctrl+I in VS Code)
2. Copy entire COPILOT_INSTRUCTION.py text into Copilot
3. Ask: "Based on this instruction, what are the immediate first steps?"
4. Copilot will outline a plan (should match below)

PHASE 2: Fix Critical Route (45-90 minutes)
──────────────────────────────────────────
Target: admin_routes.py line ~249 (manual-join route)

2.1. ANALYZE
    Copilot prompt:
    "Show me all places in admin_routes.py where TelegramClient is created or 
     used directly. Line numbers please."
    
    Expected: Copilot finds 1-3 locations, gives line numbers

2.2. REFACTOR join_channel_manual() route
    Copilot prompt:
    "Refactor the /channels/manual-join route in admin_routes.py to use 
     TelegramDispatcher instead of creating a separate TelegramClient. 
     Follow this pattern:
     
     - Remove: from telethon import TelegramClient
     - Add: from app.services.telegram_dispatcher import get_telegram_dispatcher, TelegramTask, TaskType
     - Extract: The async logic to _join_channel_impl(channel_input)
     - Replace: asyncio.run() with dispatcher.submit()
     - Handle: Event loop reuse with try/except RuntimeError
     
     Show before and after code, with explanations."
    
    Expected: Copilot provides complete refactored code
    Action: Copy new code to admin_routes.py
    Test: See if syntax is correct (check Python: Check Syntax)

2.3. VERIFY
    Check:
    - No "from telethon import TelegramClient" in route
    - Has "from app.services.telegram_dispatcher import"
    - Uses dispatcher.submit(TelegramTask(...))
    - Extracts operation to _join_channel_impl()

PHASE 3: Fix Other Routes (60-120 minutes)
───────────────────────────────────────────
3.1. FIND other routes
    Copilot prompt:
    "Are there other routes in admin_routes.py that use TelegramClient or 
     asyncio.run() to interact with Telegram? List them with line numbers."
    
    Expected: Copilot lists ~2-5 routes
    
3.2. BATCH REFACTOR
    Copilot prompt:
    "Show me the refactored code for [route name]. Use dispatcher pattern.
     Provide both original and refactored versions."
    
    For each route:
    - Get refactored code from Copilot
    - Replace in admin_routes.py
    - Run syntax check

PHASE 4: Update Services (120-180 minutes)
──────────────────────────────────────────
4.1. DISCOVERY SERVICE
    Copilot prompt:
    "Refactor app/services/discovery_service.py to use TelegramDispatcher 
     instead of direct client calls.
     
     Current pattern:
     async def search_global(self, keyword):
         client = await self._client_manager.get_client()
         return await client.search_global(keyword)
     
     Desired pattern: Submit to dispatcher, return result
     
     Show changed methods that use client API."
    
    Action: Apply changes to discovery_service.py

4.2. AUDIENCE SERVICE (repeat for each)
4.3. PUBLISHER SERVICE
4.4. INVITATION SERVICE

PHASE 5: Integrate with Main Loop (30-45 minutes)
────────────────────────────────────────────────
5.1. UPDATE telethon_runner.py
    Copilot prompt:
    "Update telethon_runner.py to initialize and start TelegramDispatcher 
     in the main() function.
     
     Required:
     - Import: get_telegram_dispatcher from app.services.telegram_dispatcher
     - Start: await dispatcher.start() before coordinator loop
     - Stop: await dispatcher.stop() in finally block
     - Log: Dispatcher stats on shutdown
     
     Show the changes to main()."
    
    Action: Apply changes to telethon_runner.py

PHASE 6: Cleanup (30 minutes)
────────────────────────────
6.1. FIND BLOCKING CALLS
    Copilot prompt:
    "Search the entire project for time.sleep() in async functions.
     List all occurrences and show how to replace with await asyncio.sleep()."
    
    Action: Replace all time.sleep() with await asyncio.sleep()

6.2. VERIFY NO DUPLICATE CLIENTS
    Copilot prompt:
    "Search for all TelegramClient(...) instantiations in the project.
     It should appear ONLY in:
     1. app/services/telegram_client.py (singleton creation)
     2. Nowhere else
     
     Show results and any locations that need fixing."
    
    Action: Fix any other instances

PHASE 7: Testing (60-90 minutes)
────────────────────────────────
7.1. START TELETHON RUNNER
    Terminal:
    $ python telethon_runner.py
    
    Expected logs:
    ✓ TelegramClientManager initialized
    ✓ TelegramDispatcher initialized
    ✓ TelegramDispatcher started
    ✓ Services initialized
    ✓ Coordinator running
    ✓ [DISPATCH] Task accepted messages

7.2. TEST ROUTES
    - Open web admin interface
    - Try /channels/manual-join
    - Manually add a channel
    - Expected: Completes without errors
    - Check logs: [DISPATCH] messages appear

7.3. AUTOMATED TESTS
    Copilot prompt:
    "Create a test file test_dispatcher_integration.py that:
     1. Tests dispatcher submissions work correctly
     2. Verifies single client instance
     3. Tests concurrent service access
     4. Monitors for lock conflicts
     
     Provide pytest test cases."
    
    Action: Run tests, verify all pass


💡 COPILOT PROMPTS REFERENCE
─────────────────────────────

ANALYSIS PROMPTS:
"""
Show me all uses of TelegramClient or asyncio in [file.py]
What are the Telegram API calls in [function]?
List all async/await patterns in this file
Where are event handlers registered?
"""

REFACTORING PROMPTS:
"""
Refactor [function] to use TelegramDispatcher instead of direct client
Show me how to extract [nested_function] to use dispatcher
Convert this asyncio.run() code to use dispatcher
Replace direct client creation with dispatcher submission
"""

VERIFICATION PROMPTS:
"""
List all imports of TelegramClient in the project
Are there any direct TelegramClient(...) instantiations I missed?
Show me the structure of [file] - what needs dispatcher?
Verify this refactored code is correct
"""

TESTING PROMPTS:
"""
Create pytest tests for dispatcher integration
How do I test that only one client is active?
Show me how to verify dispatcher queue is working
Create monitoring code for dispatcher metrics
"""


⚠️ COMMON PITFALLS & SOLUTIONS
───────────────────────────────

PITFALL #1: "I can't submit tasks to dispatcher from Flask routes"
SOLUTION: Use asyncio.run_coroutine_threadsafe() to submit to the running loop
          See ADMIN_ROUTES_REFACTORING.py for example

PITFALL #2: "Dispatcher not initialized when testing routes"
SOLUTION: Make sure telethon_runner.py is running with dispatcher.start()
          Dispatcher is global singleton, available after await get_..._dispatcher()

PITFALL #3: "Services need to know about dispatcher configuration"
SOLUTION: Services don't need to know - get it once with _get_dispatcher()
          Reuse cached instance (self._dispatcher = None, lazy load)

PITFALL #4: "How do I return data from dispatcher tasks?"
SOLUTION: Wrap result in TaskResult dataclass with success/data/error fields
          Return serializable data (dict), not ORM objects

PITFALL #5: "Timeout errors when dispatcher is overloaded"
SOLUTION: Adjust timeout per task type (searches longer, posts shorter)
          Monitor dispatcher stats: dispatcher.get_stats()
          Add queue metrics to logs


✅ VERIFICATION CHECKLIST
──────────────────────────

After completing refactoring, verify:

[ ] admin_routes.py
    [ ] No "from telethon import TelegramClient"
    [ ] Uses dispatcher.submit() for all Telegram operations
    [ ] All implementations in _*_impl() functions
    
[ ] Services (discovery, audience, publisher, invitation)
    [ ] Use dispatcher instead of direct client
    [ ] Have _dispatch_telegram_op() helper
    [ ] No direct TelegramClient creation
    
[ ] telethon_runner.py
    [ ] Initializes dispatcher in main()
    [ ] Starts dispatcher with await dispatcher.start()
    [ ] Stops dispatcher on shutdown
    [ ] Logs dispatcher stats
    
[ ] Code quality
    [ ] No time.sleep() in async functions
    [ ] No threading mixed with asyncio
    [ ] All imports resolve (no ImportError)
    [ ] Syntax valid (Python check passes)
    
[ ] Testing
    [ ] telethon_runner.py starts without errors
    [ ] Web routes work (manual-join, etc.)
    [ ] Logs show [DISPATCH] messages
    [ ] No "TelegramClient is not connected" errors
    [ ] No "Another session using this client" errors
    
[ ] Performance
    [ ] Operations complete faster (no duplicate clients)
    [ ] No lock contention errors
    [ ] Dispatcher metrics show completed tasks
    [ ] Services run without timing out


🎓 WHAT YOU'VE ACCOMPLISHED
───────────────────────────

After this refactoring, you will have:

✅ Single TelegramClient managed by singleton TelegramClientManager
✅ All Telegram operations serialized through TelegramDispatcher
✅ No conflicting client instances
✅ No session file lock contention
✅ Consistent Telegram API state across operations
✅ Proper async/await patterns throughout
✅ Production-ready orchestration
✅ Scalable architecture (easy to add more operations)
✅ Comprehensive error handling
✅ Observable system (can monitor dispatcher metrics)


📚 REFERENCE DOCUMENTS
──────────────────────

1. COPILOT_INSTRUCTION.py
   → Full instruction template for Copilot
   → Complete architecture explanation
   → Step-by-step migration guide
   
2. ADMIN_ROUTES_REFACTORING.py
   → Before/after code examples
   → Key changes explained
   → Routes to audit checklist
   
3. dispatcher_integration_guide.py
   → Pattern examples for each service
   → Helper method templates
   → Migration checklist


🆘 IF SOMETHING GOES WRONG
──────────────────────────

1. "Import error: No module named 'telegram_dispatcher'"
   → Make sure telegram_dispatcher.py exists in app/services/
   → Check file permissions
   
2. "Dispatcher not finding running loop"
   → Verify telethon_runner.py is running
   → Check if dispatcher.start() was called
   → See event loop integration section
   
3. "Services still creating their own clients"
   → Search for: TelegramClient( in modified files
   → Verify imports changed from TelegramClient to dispatcher
   → Check _get_dispatcher() method added
   
4. "Timeout errors"
   → Increase timeout in TelegramTask(timeout=N)
   → Monitor dispatcher.get_stats()
   → Check for long-running operations blocking the queue
   
5. "Code changes don't apply"
   → Verify telethon_runner.py restarted
   → Clear Python cache: find . -name __pycache__ -type d -exec rm -rf {} +
   → Reload Python module with Ctrl+Shift+P → Python: Clear Cache


🏁 NEXT STEPS
──────────────

1. Copy COPILOT_INSTRUCTION.py into GitHub Copilot Chat
2. Follow the prompts Copilot generates
3. Apply changes file by file, testing after each file
4. Run telethon_runner.py in terminal
5. Test routes in web browser
6. Verify logs show [DISPATCH] messages
7. Monitor dispatcher metrics
8. Deploy to production

═════════════════════════════════════════════════════════════════════════════

GOOD LUCK! You're fixing the architectural issue that's been causing
conflicts in your Telegram automation. After this, the system will be
stable, scalable, and production-ready.

═════════════════════════════════════════════════════════════════════════════
'''

print(QUICK_START)


# Additional: Create a file with useful Copilot prompts

COPILOT_PROMPTS = '''
📋 COPY-PASTE COPILOT PROMPTS
═════════════════════════════════════════════════════════════════════════════

These are ready-to-use prompts for GitHub Copilot Chat. Copy any of these
and paste into Copilot to get specific refactoring help.


🔍 ANALYSIS PROMPTS
───────────────────

1. Find all TelegramClient usage:
"""
Search admin_routes.py for every location where TelegramClient is created, 
imported, or used. List line numbers and the specific usage context.
Also search for asyncio.run() calls and what they contain.
"""

2. Identify blocking code:
"""
Find all instances of time.sleep() in async functions in the project.
Show the file, line number, and duration of sleep.
Also find any threading.Thread usage in async contexts.
"""

3. Discover event handler patterns:
"""
In conversation_service.py, show me every place where event handlers are 
registered to the TelegramClient. How are they registered?
"""


🔧 REFACTORING PROMPTS (Copy & Adapt)
──────────────────────────────────────

4. Refactor a specific route:
"""
Refactor the route at app/routes/admin_routes.py lines 215-330 (join_channel_manual).

Current pattern:
- Creates new TelegramClient inside asyncio.run()
- Loads session, joins channel, saves to database
- Blocks request until complete

New pattern:
- Submit to TelegramDispatcher
- Use asyncio.run_coroutine_threadsafe() for event loop integration
- Extract logic to _join_channel_impl(channel_input)
- Return serializable dict, not ORM object

Show the complete refactored route code with all imports.
"""

5. Add dispatcher helpers to a service:
"""
Update discovery_service.py to use TelegramDispatcher:

1. Add to __init__: self._dispatcher = None
2. Add method: async def _get_dispatcher(self) -> TelegramDispatcher
3. Add method: async def _dispatch_telegram_op(task_type, operation, *args, **kwargs)
4. Replace all "client = await self._client_manager.get_client()" and 
   "result = await client.api_call()" with "await self._dispatch_telegram_op(...)"

Show the modified methods and explain the pattern.
"""

6. Convert blocking calls to async:
"""
In the codebase, replace all time.sleep() calls with await asyncio.sleep().
Also look for threading patterns mixed with asyncio and explain how to fix them.

Show all instances found and the corrected code.
"""


🧪 TESTING & VERIFICATION PROMPTS
──────────────────────────────────

7. Create dispatcher integration tests:
"""
Create a pytest test file test_dispatcher_integration.py that:

1. Tests that TelegramDispatcher can accept and execute tasks
2. Verifies that multiple concurrent tasks are serialized (not parallel)
3. Tests task timeout handling
4. Verifies TaskResult contains success/data/error
5. Tests graceful shutdown

Use fixtures for setup/teardown.
"""

8. Verify refactoring completeness:
"""
After refactoring to use TelegramDispatcher, verify:

1. No direct TelegramClient(...) instantiation except in telegram_client.py
2. All admin routes use dispatcher.submit() for Telegram operations
3. All services have _get_dispatcher() method
4. No asyncio.run() calls except for test utilities
5. No time.sleep() in async functions
6. All imports are correct (no ImportError anywhere)

Search the entire project and report any violations.
"""


🚀 INTEGRATION PROMPTS
──────────────────────

9. Update main event loop:
"""
Update telethon_runner.py's main() function to:

1. Initialize TelegramDispatcher singleton: 
   dispatcher = await get_telegram_dispatcher()
   
2. Start dispatcher before coordinator:
   await dispatcher.start()
   logger.info('✅ TelegramDispatcher started')
   
3. Stop dispatcher on shutdown (in finally block):
   await dispatcher.stop()
   stats = dispatcher.get_stats()
   logger.info(f'📊 Final stats: {stats}')

Show the updated main() function.
"""

10. Add dispatcher logging:
"""
Add detailed logging to track dispatcher operations:

1. Log when tasks are submitted: "[DISPATCH] Task submitted..."
2. Log when tasks start: "[DISPATCH] Task started..."
3. Log when tasks complete: "[DISPATCH] Task completed - success/error..."
4. Log metrics: "[DISPATCH] Stats - executed:X, failed:Y, success_rate:Z%"

Show the logging additions and where to add them.
"""


📊 AUDIT PROMPTS
────────────────

11. Complete refactoring audit:
"""
Audit the complete refactoring for:

1. admin_routes.py - list all Telegram operations and how they're handled
2. Services (discovery, audience, publisher, invitation) - verify dispatcher usage
3. Event handlers in conversation_service - verify integration pattern
4. telethon_runner.py - verify dispatcher init/shutdown
5. Dependencies - ensure no circular imports
6. Imports - ensure all dispatcher imports exist

For each file, show if it's ✅ CORRECT or ❌ NEEDS FIXING.
"""

12. Performance verification:
"""
Create a checklist to verify dispatcher performance:

1. Measure startup time with/without dispatcher
2. Measure throughput (operations per second)
3. Check for deadlocks (operations completing in time)
4. Monitor queue length during heavy load
5. Verify single client instance (lsof on session file)

Show monitoring code.
"""


💬 CONVERSATION STARTERS FOR COPILOT
─────────────────────────────────────

13. Start full refactoring conversation:
"""
I'm refactoring a Telegram bot project from multiple TelegramClient instances
to use a centralized TelegramDispatcher (asyncio.Queue based).

The problem: Each route and service creates its own TelegramClient, causing
session file locks and connection conflicts.

The solution: Single client accessed through dispatcher singleton.

I have:
- app/services/telegram_client.py (singleton manager)
- app/services/telegram_dispatcher.py (queue-based dispatcher)
- telethon_runner.py (main async loop)
- app/routes/admin_routes.py (web routes with direct client creation)
- app/services/discovery_service.py, audience_service.py, etc.

I need to:
1. Refactor admin_routes.py to use dispatcher
2. Update all services to use dispatcher
3. Integrate dispatcher into telethon_runner.py
4. Test everything works correctly

Where should I start?
"""

14. Ask for pattern review:
"""
I have a pattern for using TelegramDispatcher in services:

async def _get_dispatcher(self) -> TelegramDispatcher:
    if self._dispatcher is None:
        self._dispatcher = await get_telegram_dispatcher()
    return self._dispatcher

async def search_channels(self, keyword):
    dispatcher = await self._get_dispatcher()
    task = TelegramTask(
        task_type=TaskType.SEARCH,
        operation=self._search_impl,
        args=(keyword,)
    )
    result = await dispatcher.submit(task)
    return result.data if result.success else None

Is this the right pattern? Any improvements?
"""


═════════════════════════════════════════════════════════════════════════════

Copy any of these prompts to GitHub Copilot Chat and it will help you
refactor your project step by step.
'''

print("\n" + "="*80)
print(COPILOT_PROMPTS)
