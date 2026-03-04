#!/usr/bin/env python3
"""Standalone script to load metagraph data - called as subprocess to avoid asyncio/threading issues."""
import json
import sys

def load_metagraph(netuid: int = 71):
    """Load metagraph and return JSON."""
    import traceback
    try:
        from bittensor.core.metagraph import Metagraph
        network = "finney"
        metagraph = Metagraph(netuid=netuid, network=network, lite=False, sync=True)
        
        uids = metagraph.uids
        hotkeys = metagraph.hotkeys
        coldkeys = metagraph.coldkeys
        incentives = metagraph.I
        emissions = metagraph.E
        validator_permit = getattr(metagraph, "validator_permit", None)
        
        # Get immunity data - use registration block, not last_update
        current_block = metagraph.block
        block_at_registration = metagraph.block_at_registration
        
        # Get immunity period from subtensor
        immunity_period = 10000
        try:
            subnet_info = metagraph.subtensor.get_subnet_hyperparameters(netuid)
            immunity_period = subnet_info.immunity_period
        except:
            pass
        
        n = len(uids)
        if validator_permit is None:
            validator_permit = [False] * n
            
        hotkeyToUid = {}
        uidToHotkey = {}
        hotkeyToColdkey = {}
        coldkeyToHotkeys = {}
        emissions_dict = {}
        incentives_dict = {}
        isValidator = {}
        isImmune = {}
        minerAge = {}
        
        for i in range(n):
            hk = hotkeys[i]
            uid = int(uids[i].item()) if hasattr(uids[i], "item") else int(uids[i])
            ck = coldkeys[i]
            em = float(emissions[i].item()) if hasattr(emissions[i], "item") else float(emissions[i])
            inc = float(incentives[i].item()) if hasattr(incentives[i], "item") else float(incentives[i])
            val = bool(validator_permit[i].item()) if hasattr(validator_permit[i], "item") else bool(validator_permit[i])
            
            # Calculate immunity based on registration block (not last_update)
            reg_block = int(block_at_registration[i].item()) if hasattr(block_at_registration[i], "item") else int(block_at_registration[i])
            blocks_since_registration = current_block - reg_block
            is_immune = blocks_since_registration < immunity_period
            
            hotkeyToUid[hk] = uid
            uidToHotkey[str(uid)] = hk
            hotkeyToColdkey[hk] = ck
            coldkeyToHotkeys.setdefault(ck, []).append(hk)
            emissions_dict[hk] = em
            incentives_dict[hk] = inc
            isValidator[hk] = val
            isImmune[hk] = is_immune
            minerAge[hk] = blocks_since_registration
        
        return {
            "hotkeyToUid": hotkeyToUid,
            "uidToHotkey": uidToHotkey,
            "hotkeyToColdkey": hotkeyToColdkey,
            "coldkeyToHotkeys": coldkeyToHotkeys,
            "emissions": emissions_dict,
            "incentives": incentives_dict,
            "isValidator": isValidator,
            "isImmune": isImmune,
            "minerAge": minerAge,
            "totalNeurons": n,
            "netuid": netuid,
            "currentBlock": current_block,
            "immunityPeriod": immunity_period,
            "error": None,
        }
    except Exception as e:
        return {
            "hotkeyToUid": {},
            "uidToHotkey": {},
            "hotkeyToColdkey": {},
            "coldkeyToHotkeys": {},
            "emissions": {},
            "incentives": {},
            "isValidator": {},
            "isImmune": {},
            "minerAge": {},
            "totalNeurons": 0,
            "netuid": netuid,
            "currentBlock": 0,
            "immunityPeriod": 10000,
            "error": str(e) + "\n" + traceback.format_exc(),
        }

if __name__ == "__main__":
    netuid = int(sys.argv[1]) if len(sys.argv) > 1 else 71
    result = load_metagraph(netuid)
    
    # Convert numpy types to Python types for JSON serialization
    def convert_to_native(obj):
        if hasattr(obj, 'item'):
            return obj.item()
        elif isinstance(obj, dict):
            return {k: convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native(i) for i in obj]
        return obj
    
    result = convert_to_native(result)
    print(json.dumps(result))
