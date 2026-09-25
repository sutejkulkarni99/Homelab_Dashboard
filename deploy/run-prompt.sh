#!/bin/bash
INBOX="$HOME/Projects/inbox"
OUTBOX="$HOME/Projects/outbox"
ARCHIVE="$HOME/Projects/archive"
LOGS="$HOME/Projects/logs"
STATUS_LOCAL="$HOME/Projects/.status.json"
STATUS_SHARE="/mnt/HomeLab_Share/Projects/.status.json"
HISTORY="$HOME/Projects/history.jsonl"

write_status() {
  python3 -c "
import json, sys, datetime, shutil, os
s, t, m, st, fi, du = sys.argv[1:7]
d = {'state': s, 'task': t, 'model': m, 'started': st if st != 'null' else None, 'finished': fi if fi != 'null' else None, 'duration_s': int(du) if du != 'null' else None, 'host': os.uname().nodename, 'updated_at': datetime.datetime.now().isoformat()}
open('$STATUS_LOCAL', 'w').write(json.dumps(d))
try: shutil.copy('$STATUS_LOCAL', '$STATUS_SHARE')
except: pass
" "$1" "$2" "$3" "$4" "$5" "$6" 2>/dev/null
}

append_history() {
  python3 -c "
import json, sys
tid, tf, mod, st, fi, du, sts, rf, prompt = sys.argv[1:10]
open('$HISTORY', 'a').write(json.dumps({'task_id': tid, 'task_file': tf, 'model': mod, 'started': st, 'finished': fi, 'duration_s': int(du), 'status': sts, 'result_file': rf, 'prompt': prompt}) + '\n')
" "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" 2>/dev/null
}

echo "[$(date)] Watcher started (polling + history)"
write_status idle "" "" null null null
PROCESSING=""
while true; do
  for f in "$INBOX"/*.md; do
    [ -e "$f" ] || continue
    FILE=$(basename "$f")
    [[ "$FILE" == "$PROCESSING" ]] && continue
    PROCESSING="$FILE"
    MODEL=$(head -1 "$f" | grep -oP '(?<=model: )[a-z-]+')
    MODEL=${MODEL:-fast}
    PROMPT_TEXT=$(tail -n +2 "$f" | head -c 2000)
    echo "[$(date)] Processing: $FILE (model=$MODEL)"
    START_TS=$(date -Iseconds)
    START_EPOCH=$(date +%s)
    write_status running "$FILE" "$MODEL" "$START_TS" null null
    tail -n +2 "$f" | claude -p --model "$MODEL" --output-format text --dangerously-skip-permissions > "$OUTBOX/${FILE%.md}-result.txt" 2> "$LOGS/${FILE%.md}-stderr.log"
    EXIT=$?
    END_EPOCH=$(date +%s)
    DURATION=$((END_EPOCH - START_EPOCH))
    END_TS=$(date -Iseconds)
    STATUS_VAL="done"
    [ $EXIT -ne 0 ] && STATUS_VAL="failed"
    [ ! -s "$OUTBOX/${FILE%.md}-result.txt" ] && STATUS_VAL="failed"
    write_status "$STATUS_VAL" "$FILE" "$MODEL" "$START_TS" "$END_TS" "$DURATION"
    append_history "$(date +%Y%m%d-%H%M%S)-$FILE" "$FILE" "$MODEL" "$START_TS" "$END_TS" "$DURATION" "$STATUS_VAL" "${FILE%.md}-result.txt" "$PROMPT_TEXT"
    mv "$f" "$ARCHIVE/$(date +%Y%m%d-%H%M%S)-$FILE" 2>/dev/null
    echo "[$(date)] Done: $FILE (exit=$EXIT, ${DURATION}s)"
    PROCESSING=""
  done
  sleep 5
done
