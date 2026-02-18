import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app
from app.models import AppConfig
from app.services.prompt_builder import get_prompt_builder

app = create_app()
with app.app_context():
    print("\nINSTRUCTIONS TEST RESULTS")
    print("=" * 60)
    dm = AppConfig.get('openai_prompt_conversation')
    ch = AppConfig.get('openai_prompt_channel_comments')
    pb = get_prompt_builder()
    prompt = pb.build_system_prompt(user_language="en")
    
    tests = [
        ("DM instructions loaded", bool(dm)),
        ("Channel instructions loaded", bool(ch)),
        ("Instructions in system prompt", bool(dm and dm in prompt)),
    ]
    
    for name, result in tests:
        print(f"[{'PASS' if result else 'FAIL'}] {name}")
    
    print("=" * 60)
    if all(r for _, r in tests):
        print("SUCCESS: All tests passed!")
    else:
        print("FAILED: Some tests failed")
