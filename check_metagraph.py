"""
Quick script to check what attributes are available in Bittensor Metagraph
"""
from bittensor.core.metagraph import Metagraph

# Load a small metagraph to inspect
netuid = 71
network = "finney"

print("Loading metagraph...")
metagraph = Metagraph(netuid=netuid, network=network, lite=True, sync=True)

print("\nAvailable attributes:")
for attr in dir(metagraph):
    if not attr.startswith('_'):
        print(f"  - {attr}")

print("\nKey attributes:")
print(f"  UIDs: {type(metagraph.uids)} - {len(metagraph.uids)} items")
print(f"  Hotkeys: {type(metagraph.hotkeys)} - {len(metagraph.hotkeys)} items")
print(f"  Block: {metagraph.block if hasattr(metagraph, 'block') else 'N/A'}")

# Check for immunity-related attributes
if hasattr(metagraph, 'active'):
    print(f"  Active: {type(metagraph.active)} - {len(metagraph.active)} items")
    print(f"    Sample values: {metagraph.active[:5]}")

if hasattr(metagraph, 'last_update'):
    print(f"  Last Update: {type(metagraph.last_update)} - {len(metagraph.last_update)} items")
    print(f"    Sample values: {metagraph.last_update[:5]}")

# Check subtensor for immunity period
if hasattr(metagraph, 'subtensor'):
    print(f"\n  Subtensor available: {metagraph.subtensor}")
    if hasattr(metagraph.subtensor, 'immunity_period'):
        try:
            immunity = metagraph.subtensor.immunity_period(netuid=netuid)
            print(f"  Immunity Period: {immunity} blocks")
        except Exception as e:
            print(f"  Error getting immunity period: {e}")
