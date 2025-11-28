import os
import asyncio
import random
import time
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Tuple, Optional

app = FastAPI()

# --- Configuration ---
ROLE = os.getenv("ROLE", "follower")  # 'leader' or 'follower'
FOLLOWERS_LIST = os.getenv("FOLLOWERS", "").split(
    ",") if os.getenv("FOLLOWERS") else []
# Delays in seconds
MIN_DELAY = float(os.getenv("MIN_DELAY", "0.0001"))
MAX_DELAY = float(os.getenv("MAX_DELAY", "0.001"))
# Default quorum (can be updated dynamically for the test)
current_write_quorum = int(os.getenv("WRITE_QUORUM", "1"))

# --- Storage ---
# Store structure: {key: (value, timestamp)}
# This allows us to track when each write occurred and prevent out-of-order updates
store: Dict[str, Tuple[str, float]] = {}

# --- Models ---


class WriteRequest(BaseModel):
    key: str
    value: str
    # Optional - leader will generate if not provided
    timestamp: Optional[float] = None


class ConfigRequest(BaseModel):
    quorum: int


# --- HTTP Client ---
# Using a shared client for connection pooling
client = httpx.AsyncClient()


@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()

# --- Endpoints ---


@app.get("/health")
async def health():
    return {"status": "ok", "role": ROLE}


@app.get("/read/{key}")
async def read_key(key: str):
    if key in store:
        value, timestamp = store[key]
        return {"key": key, "value": value, "timestamp": timestamp}
    raise HTTPException(status_code=404, detail="Key not found")


@app.get("/read_all")
async def read_all():
    # for compatibility with tests)
    return {key: value for key, (value, timestamp) in store.items()}


@app.delete("/clear")
async def clear_store():
    """Clear all data from the store."""
    store.clear()
    return {"status": "cleared", "role": ROLE}

# --- Follower Logic ---
if ROLE == "follower":
    @app.post("/replication")
    async def replicate(data: WriteRequest):
        # Only apply the update if it's newer than what we have
        # This prevents out-of-order updates from overwriting newer data
        if data.key in store:
            current_value, current_timestamp = store[data.key]
            if data.timestamp > current_timestamp:
                # Newer update - apply it
                store[data.key] = (data.value, data.timestamp)
                return {"status": "ack", "applied": True}
            else:
                # Stale update - ignore it
                return {"status": "ack", "applied": False, "reason": "stale_timestamp"}
        else:
            # New key - apply it
            store[data.key] = (data.value, data.timestamp)
            return {"status": "ack", "applied": True}

# --- Leader Logic ---
if ROLE == "leader":

    # Endpoint to change quorum dynamically for the lab analysis
    @app.post("/config")
    async def update_config(cfg: ConfigRequest):
        global current_write_quorum
        current_write_quorum = cfg.quorum
        return {"status": "updated", "quorum": current_write_quorum}

    async def send_replication(follower_url: str, data: WriteRequest):
        try:
            # 1. Simulate Network Lag (Before sending)
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            await asyncio.sleep(delay)

            # 2. Send Request
            resp = await client.post(f"{follower_url}/replication", json=data.model_dump())
            resp.raise_for_status()
            return True
        except Exception as e:
            print(f"Failed to replicate to {follower_url}: {e}")
            return False

    @app.post("/write")
    async def write_key(data: WriteRequest):
        # Generate timestamp if not provided (client writes don't include timestamp)
        if data.timestamp is None:
            data.timestamp = time.time()

        # 1. Write locally first with timestamp
        store[data.key] = (data.value, data.timestamp)

        # 2. Replicate to followers concurrently
        if not FOLLOWERS_LIST or FOLLOWERS_LIST == ['']:
            return {"status": "written_local_only"}

        # create tasks for all followers
        tasks = [send_replication(url, data) for url in FOLLOWERS_LIST]

        # 3. wait for Quorum
        # we use as_completed to return as soon as we hit the quorum count
        required_acks = current_write_quorum

        # we gather all tasks, but we want to respond as soon as 'required_acks' succeed.
        # standard asyncio.gather waits for all. We need a smarter approach for latency analysis.
        finished_acks = 0

        # if quorum is 0 or 1 (local write is 1), we might return immediately,
        # but usually Quorum implies "Remote Confirmations" in this context?
        # let's assume Quorum includes the Leader's own write.
        # if Quorum = 2, we need Leader (done) + 1 Follower.

        needed_remote_acks = max(0, required_acks)

        if needed_remote_acks == 0:
            # Fire and forget replication for remaining consistency
            asyncio.gather(*tasks)
            return {"status": "success", "quorum_met": True}

        # execute concurrently
        for coro in asyncio.as_completed(tasks):
            success = await coro
            if success:
                finished_acks += 1

            if finished_acks >= needed_remote_acks:
                break

        # Note: The remaining tasks continue running in the background in real systems,
        # but here we awaited the specific count.

        if finished_acks >= needed_remote_acks:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=500, detail="Write quorum not met")
