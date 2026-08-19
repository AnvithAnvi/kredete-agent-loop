import json
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from models import get_db, init_db
from tools import web_search, write_file, TOOL_COSTS

app = FastAPI()
init_db()

# ---- Hard limits: this is what stops a run from looping forever ----
MAX_STEPS = 5
MAX_CREDITS = 40
MAX_RETRIES_PER_STEP = 2


class RunRequest(BaseModel):
    goal: str
    force_fail_step: int | None = None  # for testing: which step (1-indexed) should fail


def run_step(step_num: int, goal: str, force_fail: bool) -> dict:
    """Executes one step of the agent. Step 1 = search, step 2 = write file."""
    if step_num == 1:
        return web_search(goal, force_fail=force_fail)
    elif step_num == 2:
        return write_file(f"summary of: {goal}", force_fail=force_fail)
    else:
        raise RuntimeError("no more steps defined")


@app.post("/runs")
def create_run(req: RunRequest, idempotency_key: str = Header(...)):
    db = get_db()

    # --- 1. Idempotency check: have we already handled this exact request? ---
    existing = db.execute(
        "SELECT * FROM runs WHERE idempotency_key = ?", (idempotency_key,)
    ).fetchone()
    if existing:
        db.close()
        return {
            "run_id": existing["id"],
            "status": existing["status"],
            "credits_spent": existing["credits_spent"],
            "steps": json.loads(existing["steps_json"]),
            "result": existing["result"],
            "note": "returned existing run (idempotency key already seen)",
        }

    # --- 2. New run: create the record ---
    run_id = str(uuid.uuid4())
    credits_spent = 0
    steps_log = []
    status = "in_progress"
    result = None

    total_steps = 2  # our fixed pipeline: search -> write_file

    for step_num in range(1, total_steps + 1):
        # --- Loop/cost guard: stop if we'd exceed our caps ---
        if step_num > MAX_STEPS:
            status = "failed"
            steps_log.append({"step": step_num, "error": "max steps exceeded"})
            break
        if credits_spent + TOOL_COSTS.get(
            "web_search" if step_num == 1 else "write_file", 0
        ) > MAX_CREDITS:
            status = "failed"
            steps_log.append({"step": step_num, "error": "max credits exceeded"})
            break

        force_fail = req.force_fail_step == step_num
        attempt = 0
        last_error = None

        # --- Bounded retry on this step ---
        while attempt <= MAX_RETRIES_PER_STEP:
            try:
                step_result = run_step(step_num, req.goal, force_fail)
                credits_spent += step_result["cost"]
                steps_log.append({
                    "step": step_num,
                    "tool": step_result["tool"],
                    "output": step_result["output"],
                    "cost": step_result["cost"],
                    "attempt": attempt + 1,
                })
                last_error = None
                break
            except RuntimeError as e:
                last_error = str(e)
                attempt += 1

        if last_error:
            # Step failed after retries: stop the run, keep credits already spent
            status = "failed"
            steps_log.append({
                "step": step_num,
                "error": last_error,
                "attempts": attempt,
                "note": "step failed after retries; credits already spent on prior steps are NOT refunded",
            })
            break
    else:
        # loop completed all steps without breaking
        status = "completed"
        result = f"Goal '{req.goal}' completed successfully."

    db.execute(
        """INSERT INTO runs (id, idempotency_key, goal, status, credits_spent, steps_json, result, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, idempotency_key, req.goal, status, credits_spent,
            json.dumps(steps_log), result, datetime.now(timezone.utc).isoformat(),
        ),
    )
    db.commit()
    db.close()

    return {
        "run_id": run_id,
        "status": status,
        "credits_spent": credits_spent,
        "steps": steps_log,
        "result": result,
    }


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    db = get_db()
    row = db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run_id": row["id"],
        "status": row["status"],
        "credits_spent": row["credits_spent"],
        "steps": json.loads(row["steps_json"]),
        "result": row["result"],
    }


app.mount("/", StaticFiles(directory="static", html=True), name="static")