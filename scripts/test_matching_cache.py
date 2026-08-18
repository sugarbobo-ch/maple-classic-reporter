import sys
from maple_reporter.sanctions.repository import SanctionRepository
from maple_reporter.sanctions.matcher import find_matching_bulletin

sys.stdout.reconfigure(encoding='utf-8')

repo = SanctionRepository()
cache = repo.load_cache()
all_bulletins = list(cache.bulletins.values())
print(f"Loaded {len(all_bulletins)} cached bulletins:")
for b in all_bulletins:
    print(f"  Bid {b.bid} ({b.publication_date}): {len(b.entries)} entries")

candidate = find_matching_bulletin("下次我還要玩", "2026-08-17", all_bulletins)
print("Matching result for '下次我還要玩':", candidate)
if candidate:
    print(f"  Matched: {candidate.entry.masked_name} | Result: {candidate.entry.result} | Date: {candidate.bulletin.publication_date}")
