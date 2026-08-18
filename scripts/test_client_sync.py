import sys
import threading
from maple_reporter.sanctions.official_api import OfficialSanctionApiClient
from maple_reporter.sanctions.repository import SanctionRepository
from maple_reporter.utils.config import get_user_app_data_dir

sys.stdout.reconfigure(encoding='utf-8')

client = OfficialSanctionApiClient()
event = threading.Event()

# 1. Test fetching bulletin list
headers = client.fetch_bulletin_list(1, event)
print(f"fetch_bulletin_list(1) returned {len(headers)} bulletins:")
for h in headers[:5]:
    print(f"  Bid: {h.bid} | Date: {h.publication_date} | Title: {h.title}")

# 2. Test fetching detail for first bulletin
if headers:
    first = headers[0]
    detail = client.fetch_bulletin_detail(first.bid, event)
    print(f"\nfetch_bulletin_detail({first.bid}) succeeded:")
    print(f"  Title: {detail.title}")
    print(f"  PubDate: {detail.publication_date}")
    print(f"  Entries: {len(detail.entries)}")
