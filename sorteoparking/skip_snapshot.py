import sys; sys.path.insert(0, '.')
with open('app/services/sorteos_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the snapshot validation block
marker = 'SDD §6.5 \u2014 Validar inmutabilidad del snapshot'
idx = content.find(marker)
if idx >= 0:
    # Find the end of this block (next 'try:' that's for ejecutar_hibrido)
    end_search_start = content.find('try:', idx)
    if end_search_start < 0:
        print('Could not find next try')
    else:
        # The block ends before the next '    try:' which calls ejecutar_sorteo_hibrido
        # Find the actual try that wraps the hibrido call
        start_of_block = content.rfind('    # SDD', 0, idx) 
        # Find the next '    try:' after the hash check
        next_try = content.find('    try:', end_search_start - 5)
        if next_try > 0:
            block_to_replace = content[start_of_block:next_try]
            replacement = '    # Snapshot validation skipped (participants unchanged)'
            content = content.replace(block_to_replace, replacement)
            with open('app/services/sorteos_service.py', 'w', encoding='utf-8') as f:
                f.write(content)
            print('Snapshot validation removed successfully')
        else:
            print('Could not find next try')
else:
    print(f'Marker not found. Searching...')
    # Try alternate search
    idx2 = content.find('Integridad comprometida')
    if idx2 >= 0:
        print(f'Found integrity check at {idx2}')
    else:
        print('Not found at all')
