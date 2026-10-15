"""Small current-data inputs for the Artifact pipeline layout."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'ipo_lib'))
from build_xlsx import load,PIPE_COLS,listify
from pipeline_dedupe import status_asof
pipe=load()[3];apps=json.loads((ROOT/'data/batches/phip_pipeline.json').read_text())['applications'];queue=[a for a in apps if not a.get('has_phip')][:30];q=9+len(pipe)
data=dict(headers=[c[0] for c in PIPE_COLS],pipeline=[[listify(p.get(c[1])) for c in PIPE_COLS] for p in pipe],queue=queue,queue_start=q,last_row=q+4+len(queue),subtitle='Status checked '+status_asof(ROOT))
(ROOT/'out/pipeline_layout_inputs.json').write_text(json.dumps(data,ensure_ascii=False))
print(len(pipe),'pipeline rows;',len(queue),'application rows')
