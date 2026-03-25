import os
import glob

module_map = {
    'config': 'core.config',
    'event_bus': 'core.event_bus',
    'data_manager': 'data.data_manager',
    'kis_api': 'data.kis_api',
    'screener': 'screening.screener_kr',
    'strategy': 'trading.strategy',
    'portfolio': 'trading.portfolio',
    'notifier': 'notification.notifier',
    'telegram_bot': 'notification.telegram_bot'
}

print("Refactoring imports...")
for file_path in glob.glob('**/*.py', recursive=True):
    # skip venv and test files
    if file_path.startswith('.venv'): continue
    if file_path in ['refactor_imports.py', 'tmp_fast_test.py', 'test_telegram_only.py', 'run_test.py']: continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    original = content
    for old_mod, new_mod in module_map.items():
        content = content.replace(f'from {old_mod} import', f'from {new_mod} import')
        content = content.replace(f'import {old_mod}\n', f'import {new_mod}\n')
        content = content.replace(f'import {old_mod}\r\n', f'import {new_mod}\r\n')
        
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated imports in {file_path}")

print("Done.")
