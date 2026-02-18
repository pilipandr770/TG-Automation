# CSRF Token Validation Guide

## Problem: POST /admin/instructions Returns 400

The 400 error you're seeing likely indicates a **CSRF token validation failure**. This is a security feature of Flask-WTF that prevents Cross-Site Request Forgery attacks.

## Root Cause

The issue is most likely caused by **server reloads invalidating session data**:

1. **Developer loads `/admin/instructions`** → Flask generates CSRF token and stores it in the session
2. **Flask server reloads** (due to watchdog detecting file changes) → **Session is cleared**
3. **Admin submits the form** → CSRF token in form doesn't match the (now-empty) session data
4. **Result**: 400 Bad Request (CSRF validation failed)

## Symptoms

You'll see in the logs:
```
* Detected change in '...', reloading
* Restarting with watchdog
127.0.0.1 - - [...] "POST /admin/instructions HTTP/1.1" 400 -
```

## Solutions

### Solution 1: Disable Debug Mode (Recommended for Testing)

Stop the Flask development server and restart **without** debug mode:

```bash
# Instead of:
flask run --debug

# Run:
flask run
# or
python wsgi.py
```

Without `--debug`, the server won't reload, and CSRF tokens will remain valid throughout your testing session.

### Solution 2: Refresh Page After Server Reload

If you prefer to keep debug mode:

1. Make your code change (server reloads automatically)
2. **Refresh the page** in your browser (Ctrl+R or Cmd+R)
3. **Then** submit the form

This ensures you get a new CSRF token that matches the current session.

### Solution 3: Check Browser Console

To verify CSRF token is being sent:

1. Open browser Developer Tools (F12 or Ctrl+Shift+I)
2. Go to "Network" tab
3. Submit the form
4. Click on the failed POST request
5. Go to "Request" tab
6. Look for `csrf_token` field in the form data

If it's there, good! If not, there might be a template rendering issue.

## How CSRF Protection Works

1. **GET request**: Flask renders template → `{{ csrf_token() }}` generates token based on current session
2. **POST request**: Flask validates the token in form against the token in session
3. If tokens match → Request is processed ✓
4. If tokens don't match → 400 Bad Request ✗

## Debugging: Check the Logs

After our changes, the server will log detailed CSRF errors:

```
ERROR:app:CSRF Error: The CSRF token does not match.
ERROR:app:Request path: /admin/instructions
ERROR:app:Request method: POST
ERROR:app:Form keys: ['dm_instruction', 'action', 'csrf_token']
ERROR:app:CSRF token in form: True
```

This tells us:
- Form is being submitted correctly
- CSRF token IS in the form data
- But validation is still failing (likely due to session mismatch)

## Testing the Instructions Form

### Proper Testing Procedure

1. **Stop the Flask server completely**
   ```bash
   # Press Ctrl+C in terminal running Flask
   ```

2. **Restart Flask WITHOUT debug mode**
   ```bash
   python wsgi.py
   # or
   flask run --no-reload
   ```

3. **Open the instructions page**
   - Go to http://localhost:5000/admin/instructions
   - Don't make any code changes yet

4. **Submit the form** - This should work now ✓

5. **Make a code change** if needed

6. **Stop Flask & restart** without debug mode (repeats step 2)

### Alternative: Use no-reload flag

```bash
flask run --no-reload
```

This keeps debug mode but disables automatic reloading, preventing CSRF token invalidation.

## Permanent Fix (Production)

In production, debug mode is disabled by default, so this issue won't occur. The config uses:

```python
class ProductionConfig(Config):
    DEBUG = False
```

## Verification Checklist

- [ ] CSRF token fields are in the form HTML (`<input type="hidden" name="csrf_token" ...>`)
- [ ] Form method is POST (`<form method="POST" ...>`)
- [ ] Form action is correct (`action="{{ url_for('admin.instructions') }}"`)
- [ ] Server is not reloading during form submission
- [ ] Page was loaded AFTER last Django server reload
- [ ] Browser cookies are enabled (CSRF tokens require sessions to work)
- [ ] Session data is not being cleared artificially

## If Problem Persists

1. **Clear browser cache** - Cmd+Shift+Delete (Chrome) or Ctrl+Shift+Delete (Firefox)
2. **Check SECRET_KEY** - Verify it's set in config (required for CSRF)
3. **Check logs** - Look for CSRFError messages that tell you what's wrong
4. **Restart browser** - Sometimes session cookies get corrupted
5. **Use incognito/private mode** - Rules out browser cache issues

## Technical Details

### CSRF Token Generation
```python
{{ csrf_token() }}  # Generates token based on Flask session
```

### CSRF Validation
Flask-WTF intercepts POST requests and checks:
```python
if request.form.get('csrf_token') != session.get('csrf_token'):
    raise CSRFError()  # Returns 400
```

### Why Sessions Clear on Reload
- Flask development uses in-memory sessions by default
- When the server restarts, memory is cleared
- This invalidates all CSRF tokens for current connections

## Summary

The 400 error is **not a bug** — it's Flask-WTF working as designed to protect against CSRF attacks. The issue is that the CSRF token becomes invalid when the server reloads during development.

**Fix**: Either disable auto-reload mode, or refresh the page after reload before submitting forms.
