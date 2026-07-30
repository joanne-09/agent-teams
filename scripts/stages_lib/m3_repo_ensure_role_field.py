"""Five-callable setup-stage contract for m3.repo.ensure-role-field."""
from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path
from typing import Any
from stages_lib._partitioned_settings import get_module_section

ROLE_OPTIONS = ["analyst", "architect", "rd", "qa", "em", "human"]
_M10_MODULE_ID = "m10_kanban"

def compute_target_state(ctx: Any) -> dict:
    return {"role_field_present": True, "field_name": "Role", "options": ROLE_OPTIONS}

def target_state_predicate(state: Any) -> bool:
    return isinstance(state, dict) and state.get("role_field_present") is True and state.get("field_name") == "Role" and state.get("options") == ROLE_OPTIONS

def _project_ref(ctx: Any) -> str:
    env = os.environ.get("BSP_PROJECT_REF", "")
    if env: return env
    section = get_module_section("repo-git", _M10_MODULE_ID, home=Path(ctx.home), repo_root=Path(ctx.repo_root), repo_identity=ctx.repo_identity)
    return section.get("project_ref", "") if isinstance(section, dict) else ""

def idempotency_check(ctx: Any) -> dict:
    ref=_project_ref(ctx)
    empty={"field_name":"Role","existing_options":[],"missing":ROLE_OPTIONS}
    if not ref or len(ref.split('/')) != 2:
        return {"present":False,"current_state":{**empty,"error":"project_ref not configured"}}
    owner, number=ref.split('/',1)
    try:
        result=subprocess.run(["gh","project","field-list",number,"--owner",owner,"--format","json","--limit","100"],capture_output=True,text=True,timeout=30)
        if result.returncode != 0: return {"present":False,"current_state":{**empty,"error":result.stderr.strip()}}
        raw=json.loads(result.stdout); fields=raw.get("fields", raw if isinstance(raw,list) else [])
        field=next((f for f in fields if isinstance(f,dict) and f.get("name")=="Role"),None)
        if not field: return {"present":False,"current_state":empty}
        existing=[o.get("name") for o in field.get("options",[]) if isinstance(o,dict)]
        missing=[name for name in ROLE_OPTIONS if name not in existing]
        extra=[name for name in existing if name not in ROLE_OPTIONS]
        return {"present":not missing and not extra,"current_state":{"field_name":"Role","existing_options":existing,"missing":missing,"extra":extra}}
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:
        return {"present":False,"current_state":{**empty,"error":str(exc)}}

def executor(ctx: Any) -> dict:
    check=idempotency_check(ctx)
    if check["present"]: return {"applied":False,"message":"Role field already canonical -- no-op","side_effects":[]}
    state=check["current_state"]
    if state.get("existing_options"):
        return {"applied":False,"requires_input":True,"message":"Role field exists with a non-canonical option set; repair it in Project settings, then re-run","prompt":{"kind":"confirm-only","prompt":"Set Role options to analyst, architect, rd, qa, em, human in GitHub Project settings, then confirm.","options_source":"literal","options":[{"value":"revalidate","label":"Re-validate Role field"}]},"side_effects":[]}
    ref=_project_ref(ctx)
    if not ref or len(ref.split('/')) != 2: return {"applied":False,"message":"project_ref not configured","side_effects":[]}
    owner, number=ref.split('/',1)
    try:
        result=subprocess.run(["gh","project","field-create",number,"--owner",owner,"--name","Role","--data-type","SINGLE_SELECT","--single-select-options",','.join(ROLE_OPTIONS),"--format","json"],capture_output=True,text=True,timeout=60)
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {"applied":False,"message":f"Role field create failed: {exc}","side_effects":[]}
    if result.returncode != 0: return {"applied":False,"message":f"Role field create failed: {result.stderr.strip()}","side_effects":[]}
    return {"applied":True,"message":"Created Role single-select field with six canonical seats","side_effects":[f"created Role field on {ref}"]}

def apply_choice(ctx: Any, resolution_value: str) -> dict:
    if resolution_value != "revalidate": raise ValueError("resolution_value must be 'revalidate'")
    check=idempotency_check(ctx)
    if not check["present"]: return {"applied":False,"requires_input":True,"message":"Role field is still non-canonical","side_effects":[]}
    return {"applied":False,"message":"Role field validated","side_effects":[]}
