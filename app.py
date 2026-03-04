from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
import uvicorn
import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SN71 Session Manager")
templates = Jinja2Templates(directory="templates")

# Mount static files (for favicon and other assets)
app.mount("/asset", StaticFiles(directory="asset"), name="asset")

# Homepage: Miners page (default first load)
@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("miners.html", {"request": request})

# Miners page (also at / for homepage)
@app.get("/miners", response_class=HTMLResponse)
async def miners_page(request: Request):
    return templates.TemplateResponse("miners.html", {"request": request})

# --- Metagraph via Bittensor (configurable netuid, finney) ---
def _load_metagraph_from_bittensor(netuid: int = 71):
    """Blocking: load metagraph and return API-shaped dict for miners page. Uses lite=True for faster load."""
    import traceback
    try:
        from bittensor.core.metagraph import Metagraph
        network = "finney"
        logger.info(f"Creating Metagraph object for netuid={netuid}, network={network}")
        metagraph = Metagraph(netuid=netuid, network=network, lite=True, sync=True)
        logger.info(f"Metagraph loaded successfully with {len(metagraph.uids)} neurons")
        
        uids = metagraph.uids
        hotkeys = metagraph.hotkeys
        coldkeys = metagraph.coldkeys
        incentives = metagraph.I
        emissions = metagraph.E
        validator_permit = getattr(metagraph, "validator_permit", None)
        
        # Get immunity data
        current_block = metagraph.block
        last_update = metagraph.last_update
        immunity_period = 10000  # Default
        try:
            immunity_period = metagraph.subtensor.immunity_period(netuid=netuid)
            logger.info(f"Got immunity_period: {immunity_period} blocks")
        except Exception as e:
            logger.warning(f"Could not get immunity period, using default: {e}")
        
        n = len(uids)
        if validator_permit is None:
            validator_permit = [False] * n
        # Build same shape as subnet71 API for miners page
        hotkeyToUid = {}
        uidToHotkey = {}
        hotkeyToColdkey = {}
        coldkeyToHotkeys = {}
        emissions_dict = {}
        incentives_dict = {}
        isValidator = {}
        isImmune = {}
        minerAge = {}
        
        logger.info(f"Processing {n} neurons...")
        for i in range(n):
            hk = hotkeys[i]
            uid = int(uids[i].item()) if hasattr(uids[i], "item") else int(uids[i])
            ck = coldkeys[i]
            em = float(emissions[i].item()) if hasattr(emissions[i], "item") else float(emissions[i])
            inc = float(incentives[i].item()) if hasattr(incentives[i], "item") else float(incentives[i])
            val = bool(validator_permit[i].item()) if hasattr(validator_permit[i], "item") else bool(validator_permit[i])
            
            # Calculate immunity status
            last_update_block = int(last_update[i].item()) if hasattr(last_update[i], "item") else int(last_update[i])
            age_blocks = current_block - last_update_block
            is_immune = age_blocks < immunity_period
            
            hotkeyToUid[hk] = uid
            uidToHotkey[str(uid)] = hk
            hotkeyToColdkey[hk] = ck
            coldkeyToHotkeys.setdefault(ck, []).append(hk)
            emissions_dict[hk] = em
            incentives_dict[hk] = inc
            isValidator[hk] = val
            isImmune[hk] = is_immune
            minerAge[hk] = age_blocks
        
        immune_count = sum(1 for v in isImmune.values() if v)
        logger.info(f"Successfully processed metagraph: {n} neurons, {immune_count} immune")
        
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
        error_msg = f"Error in _load_metagraph_from_bittensor: {e}"
        error_trace = traceback.format_exc()
        logger.error(error_msg)
        logger.error(f"Full traceback:\n{error_trace}")
        # Return error in response instead of raising
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
            "error": str(e),
        }


# Cache metagraph per netuid; TTL 2 min. Use ?refresh=1 to force fresh load.
METAGRAPH_CACHE_TTL = 120
_metagraph_cache: dict = {}  # netuid -> {"data": ..., "timestamp": ...}

def _parse_netuid(raw: Optional[str], default: int = 71) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        n = int(raw.strip())
        if n < 0 or n > 255:
            return default
        return n
    except ValueError:
        return default

@app.get("/api/metagraph-data")
async def get_metagraph_data(request: Request):
    import time
    import asyncio
    import traceback
    try:
        raw_netuid = request.query_params.get("netuid")
        netuid = _parse_netuid(raw_netuid, 71)
        current_time = time.time()
        refresh = request.query_params.get("refresh", "").lower() in ("1", "true", "yes")
        skip_cache = refresh

        cache_entry = _metagraph_cache.get(netuid)
        if not skip_cache and cache_entry and (current_time - cache_entry["timestamp"]) < METAGRAPH_CACHE_TTL:
            logger.info(f"Returning cached metagraph data for netuid={netuid}")
            return cache_entry["data"]

        # Load from Bittensor Metagraph (using subprocess to avoid asyncio/threading issues)
        logger.info(f"Loading fresh metagraph data for netuid={netuid}...")
        try:
            import subprocess
            import json
            
            # Call standalone script as subprocess with timeout
            python_path = sys.executable or "python3"
            script_path = os.path.join(os.path.dirname(__file__), "load_metagraph.py")
            
            logger.info(f"Calling subprocess: {python_path} {script_path} {netuid}")
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    python_path, script_path, str(netuid),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=5.0  # 5 seconds to start the process
            )
            
            # Wait for process to complete with 90 second timeout
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=90.0
            )
            
            if proc.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace')
                logger.error(f"Subprocess failed with code {proc.returncode}: {error_msg}")
                raise HTTPException(status_code=500, detail=f"Failed to load metagraph: {error_msg}")
            
            data = json.loads(stdout.decode('utf-8'))
            logger.info(f"Successfully loaded metagraph with {data.get('totalNeurons', 0)} neurons")
            
            if data.get("error"):
                logger.error(f"Error from subprocess: {data['error']}")
                raise HTTPException(status_code=500, detail=data["error"])
            
            _metagraph_cache[netuid] = {"data": data, "timestamp": current_time}
            return data
        except asyncio.TimeoutError:
            logger.error("Timeout error: Metagraph loading exceeded 90 seconds")
            raise HTTPException(status_code=504, detail="Metagraph loading timeout")
    except HTTPException:
        raise
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error loading metagraph from Bittensor: {e}")
        logger.error(f"Full traceback:\n{error_details}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
