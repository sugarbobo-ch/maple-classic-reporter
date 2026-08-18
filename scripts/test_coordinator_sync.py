import sys
import time
from maple_reporter.sanctions.coordinator import SanctionSyncCoordinator
from maple_reporter.sanctions.repository import SanctionRepository
from maple_reporter.sanctions.official_api import OfficialSanctionApiClient

sys.stdout.reconfigure(encoding='utf-8')

repo = SanctionRepository()
api_client = OfficialSanctionApiClient(random_delay_func=lambda a, b: 0.05) # fast test
coordinator = SanctionSyncCoordinator(repository=repo, api_client=api_client)

res = coordinator.start(trigger='manual')
print("coordinator.start result:", res.started, res.reason)

while True:
    status = coordinator.get_status()
    print(f"Status update: running={status.running} | phase={status.phase} | {status.message} ({status.current}/{status.total})")
    if not status.running:
        break
    time.sleep(0.8)

final_history = repo.load_history()
print(f"\nFinal history records ({len(final_history)} items):")
for r in final_history:
    print(f"  {r.get('suspect_id', ''):15s} | status={r.get('sanction_status', ''):12s} | ban_date={r.get('ban_date')} | match={r.get('matched_mask')}")
