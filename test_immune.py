import bittensor
from bittensor.core.metagraph import Metagraph


def get_immune_miners_only(netuid: int, network: str = "finney"):
    import bittensor
    from bittensor.core.metagraph import Metagraph

    subtensor = bittensor.subtensor(network=network)
    current_block = subtensor.block

    subnet_info = subtensor.get_subnet_hyperparameters(netuid)
    immunity_period = subnet_info.immunity_period

    metagraph = Metagraph(
        netuid=netuid,
        network=network,
        lite=False,
        sync=True
    )

    results = []

    for i in range(len(metagraph.uids)):

        # Skip validators
        if metagraph.validator_permit[i]:
            continue

        uid = int(metagraph.uids[i])
        hotkey = metagraph.hotkeys[i]

        reg_block = int(metagraph.block_at_registration[i])
        blocks_alive = current_block - reg_block

        is_immune = blocks_alive < immunity_period
        immunity_remaining = max(immunity_period - blocks_alive, 0)

        results.append({
            "uid": uid,
            "hotkey": hotkey,
            "blocks_since_registration": blocks_alive,
            "immunity_remaining_blocks": immunity_remaining,
            "is_immune": is_immune
        })

    return results

def print_summary(data):
    immune_count = sum(1 for x in data if x["is_immune"])
    total = len(data)

    print("\n========== MINER IMMUNITY STATUS ==========")
    print(f"Total miners:       {total}")
    print(f"Immune miners:      {immune_count}")
    print(f"Non-immune miners:  {total - immune_count}")
    print("===========================================\n")

    for entry in data:
        status = "IMMUNE" if entry["is_immune"] else "PRUNE-ELIGIBLE"
        print(
            f"UID {entry['uid']:>4} | "
            f"{status:<15} | "
            f"Blocks alive: {entry['blocks_since_registration']:>6} | "
            f"Remaining: {entry['immunity_remaining_blocks']:>6}"
        )


if __name__ == "__main__":
    miner_data = get_immune_miners_only(71, "finney")
    print_summary(miner_data)
