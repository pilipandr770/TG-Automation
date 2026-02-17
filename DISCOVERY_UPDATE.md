## SYSTEM UPDATE: SMART DISCOVERY WITH AUTO-REGENERATING KEYWORDS

### What's New:

✅ **COMMENTS REQUIREMENT ENFORCED**
- Discovery now ONLY subscribes to channels/groups with comments enabled
- Filters out regular channels where you can't see who comment (no discussions)
- Only joins: megagroups, gigagroups, and supergroups with = visible user discussions

✅ **AUTOMATIC KEYWORD REGENERATION**
- When a keyword finds 0 new channels for 3 consecutive cycles, it's marked as "exhausted"
- System automatically generates 3 new keyword variants on the same topic
- Example: "adult dating" → generates "dating singles", "hookup chat", "adult meet"
- Original keyword stays in DB for history, new variants continue searching
- Process repeats until reaching 45,000 channel limit

✅ **DISCOVERY MONITOR DASHBOARD**
- New page: `/admin/discovery-monitor`
- Real-time stats on:
  - Total joined channels vs practical limit (45k / 50k)
  - Active keywords vs exhausted keywords
  - Regeneration round tracking
  - Progress bar on API limit usage
  - Smart warnings when approaching limits

✅ **TELEGRAM API LIMITS TRACKING**
- Practical limit: 45,000 dialogs (channels + groups)
- System warns at 80% usage
- Prevents exceeding technical limits

### Database Changes:

**search_keywords table new fields:**
```sql
- exhausted (BOOLEAN) — marks keywords that found 0 new channels for 3+ cycles
- cycles_without_new (INTEGER) — tracks consecutive cycles without new channels
- generation_round (INTEGER) — 0=original, 1,2,3=regenerated variants
- source_keyword (VARCHAR) — tracks which original keyword this variant came from
```

### Discovery Flow (UPDATED):

```
1. Run Discovery Cycle (every 5 minutes)
   └─> For each ACTIVE keyword:
       ├─> Search Telegram via SearchRequest API
       ├─> Evaluate channels (REQUIRES comments!)
       ├─> Join qualifying channels
       └─> Track: did this keyword find new channels?

2. After each cycle:
   └─> Check if any keywords exhausted (3 cycles = 0 new)
       ├─> Mark as exhausted
       ├─> Auto-generate 3 new keyword variants
       └─> Add variants to active search list

3. Progress Tracking:
   └─> Monitor at /admin/discovery-monitor
       ├─> See joined count vs limit
       ├─> View exhausted keywords
       ├─> Check regenerated variants
       └─> Get warnings when approaching 45k limit
```

### Why Comments-Only?

**Your use case requires real user discussions:**
- Regular channels: automated posts, no reader identity
- Megagroups/Supergroups: users post, you see WHO writes WHAT
- This is where your audience actually discusses content
- You can analyze real people's interests and engage them
- Comments enable proper categorization of users (admin/bot/competitor/target)

### Example Regeneration Scenario:

```
CYCLE 1: Business goal = "adult content sales"
- Searching: "adult content", "adult dating", "NSFW groups", etc. (24 keywords)
- Found: 15 new channels
- Result: Cycles_without_new for all = 0 → cycle continues

CYCLE 2-3: Same keywords
- Found: some new, but several keywords find 0 new
- "adult chat" → cycles_without_new = 2
- "explicit content" → cycles_without_new = 2

CYCLE 4: "adult chat" hits 3 cycles without new
- Mark as EXHAUSTED
- Generate variants: "dating chat", "adult conversation", "NSFW discussion"
- Add to active keywords list
- Original "adult chat" rests but stays in DB

CYCLE 5: New variants search alongside others
- "dating chat" finds 3 new channels!
- "adult conversation" finds 5 new channels!
- Process continues...

UNTIL: 45,000 joined channels or exhaustion

FINAL RESULT: Downloaded maximum available audience from target niche
```

### Configuration:

No manual configuration needed! System is automatic:
- Comments requirement: ALWAYS ON (hardcoded as `return True`)
- Regeneration trigger: 3 consecutive cycles without new channels
- Regeneration count: 3 variants per exhausted keyword
- Telegram API limit: 45,000 (practical) / 50,000 (technical)

### Files Updated:

1. **app/models.py** — SearchKeyword model (+4 fields)
2. **app/services/discovery_service.py** — New methods:
   - `check_and_regenerate_exhausted_keywords()` — auto-regen logic
   - `_generate_keyword_variants()` — uses OpenAI to create variants
   - `check_discovery_limits()` — tracks API limits
   - Updated `run_discovery_cycle()` — tracks exhaustion + regeneration
3. **app/routes/admin_routes.py** — New endpoint:
   - `/admin/discovery-monitor` — dashboard
4. **app/templates/admin/discovery_monitor.html** — NEW template
5. **app/templates/admin/base.html** — Added menu link
6. **migrate_keywords.py** — Migration script (run once)

### What to Do Next:

1. System now requires REAL TELEGRAM CLIENT running (Telethon worker)
   - Discovery will run every 5 minutes automatically
   - Monitor progress at `/admin/discovery-monitor`

2. Initial setup:
   - Business goal is already set: "adult content sales"
   - Keywords already generated: 24 keywords
   - Channels already discovered: 39 joined, 230+ found

3. Let the system run for 24+ hours:
   - It will discover hundreds/thousands of channels
   - Auto-regenerate keywords as they exhaust
   - Build massive audience database
   - Until hitting ~45,000 channel limit

4. Once discovery is complete:
   - Run audience scan on all joined channels
   - Categorize contacts (target_audience vs bots/admins/competitors)
   - Send invitations to target audience
   - Start paid content campaigns

### Monitoring:

Check progress at:
- **Dashboard**: `/admin/discovery-monitor` (new)
- **Channels**: `/admin/channels` (shows all discovered)
- **Keywords**: `/admin/keywords` (shows regeneration status)
- **Contacts**: `/admin/contacts` (shows categorized audience)

🎯 **System is now fully autonomous and optimized for maximum audience discovery!**
