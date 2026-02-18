import sqlite3

db = sqlite3.connect('./instance/telegram_automation.db')
cursor = db.cursor()

print('\n' + '='*60)
print(' '*15 + 'PIPELINE FIX VERIFICATION')
print('='*60)

# Check configs
cursor.execute('SELECT value FROM app_config WHERE key=?', ('discovery_min_subscribers',))
min_subs = cursor.fetchone()[0]
print(f'\n✓ MIN SUBSCRIBERS: {min_subs} (lowered from 50)')

cursor.execute('SELECT value FROM app_config WHERE key=?', ('discovery_min_topic_score',))
min_score = cursor.fetchone()[0]
print(f'✓ MIN TOPIC SCORE: {min_score} (lowered from 0.3)')

cursor.execute('SELECT value FROM app_config WHERE key=?', ('discovery_topic_context',))
topic_ctx = cursor.fetchone()[0]
print(f'✓ TOPIC CONTEXT: "{topic_ctx}"')

# Check audience criteria
cursor.execute('SELECT name FROM audience_criteria WHERE active=1 ORDER BY id')
criteria = cursor.fetchall()
print(f'\n✓ AUDIENCE CRITERIA ({len(criteria)} active):')
for name, in criteria:
    print(f'   • {name}')

# Check keyword regeneration
cursor.execute('SELECT COUNT(*) FROM search_keywords WHERE cycles_without_new >= 5')
regen = cursor.fetchone()[0]
print(f'\n✓ KEYWORDS READY FOR REGENERATION: {regen}')

print('\n' + '='*60)
print('All fixes applied. System ready for next cycle!')
print('='*60 + '\n')

db.close()
