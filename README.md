
# Kredete Agent Run Loop

A minimal slice of an autonomous agent's run loop: takes a goal, executes a
short fixed pipeline of mocked tool calls (web_search -> write_file), tracks
credits spent, and returns the run's status and output.

## Run it

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open http://127.0.0.1:8000 in a browser.

## What it handles

- **Idempotency**: every request requires an `Idempotency-Key` header. A
  retried request with the same key returns the original result instead of
  re-running or re-charging.
- **Loop/cost bounds**: hard caps on both step count (`MAX_STEPS`) and total
  credits (`MAX_CREDITS`), whichever is hit first stops the run.
- **Partial failure**: a failing step is retried up to `MAX_RETRIES_PER_STEP`
  times. If it still fails, the run is marked `failed` and credits already
  spent on prior successful steps are kept, not refunded.
- **Exact credit accounting**: credits are tracked as integers throughout,
  no floating point.

## API

`POST /runs`
Headers: `Idempotency-Key: <any unique string>`
Body: `{"goal": "<text>", "force_fail_step": <1 or 2, optional>}`

`GET /runs/{run_id}` — fetch a previously created run by ID.

## Testing the three required scenarios

```bash
# 1. Normal run
curl -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-key-1" \
  -d '{"goal": "research AI agent pricing"}'

# 2. Exact same request again — proves no double-run / double-charge
curl -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-key-1" \
  -d '{"goal": "research AI agent pricing"}'

# 3. Forced partial failure — step 1 succeeds, step 2 fails,
#    credits from step 1 stay spent (not refunded)
curl -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-key-2" \
  -d '{"goal": "test partial failure", "force_fail_step": 2}'
```

Design reasoning (loop bound, failure handling, credit accounting, and the
trade-off I'm least sure about) is covered in the submitted decisions doc,
not in this repo.