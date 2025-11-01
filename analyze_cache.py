import json
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")

with open('cache.json', 'r') as f:
    data = json.load(f)

total = len(data)
print(f'📊 Total de chaves no cache.json: {total}')

prefixes = []
validos = 0
expirados = 0
agora = datetime.now(BRASILIA_TZ)

for k, v in data.items():
    prefix = '_'.join(k.split('_')[:2]) if '_' in k else k
    prefixes.append(prefix)
    
    if 'expires_at' in v:
        try:
            exp_time = datetime.fromisoformat(v['expires_at'])
            if agora <= exp_time:
                validos += 1
            else:
                expirados += 1
        except:
            validos += 1
    else:
        validos += 1

counts = Counter(prefixes)

print(f'\n✅ Itens válidos (não expirados): {validos}')
print(f'⏰ Itens expirados: {expirados}')

print('\n📦 Top 15 tipos de itens no cache:')
for tipo, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:15]:
    print(f'  {tipo}: {count}')
