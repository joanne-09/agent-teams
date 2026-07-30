from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import stages_lib.m3_repo_ensure_role_field as stage

def ctx(tmp_path): return SimpleNamespace(home=tmp_path,repo_root=tmp_path,repo_identity="owner/repo")
def result(payload, rc=0, err=""): return SimpleNamespace(returncode=rc,stdout=json.dumps(payload),stderr=err)

def test_predicate_requires_exact_contract(tmp_path):
    assert stage.target_state_predicate(stage.compute_target_state(ctx(tmp_path)))
    assert not stage.target_state_predicate({"role_field_present":True,"field_name":"Role","options":["rd"]})

def test_idempotency_accepts_canonical_field(tmp_path, monkeypatch):
    monkeypatch.setenv("BSP_PROJECT_REF","owner/7")
    fields={"fields":[{"name":"Role","options":[{"name":n} for n in stage.ROLE_OPTIONS]}]}
    with patch("subprocess.run",return_value=result(fields)) as run:
        check=stage.idempotency_check(ctx(tmp_path))
    assert check["present"] is True
    assert run.call_args.args[0][:4] == ["gh","project","field-list","7"]

def test_executor_creates_absent_field(tmp_path, monkeypatch):
    monkeypatch.setenv("BSP_PROJECT_REF","owner/7")
    with patch("subprocess.run",side_effect=[result({"fields":[]}),result({"id":"F"})]) as run:
        out=stage.executor(ctx(tmp_path))
    assert out["applied"] is True
    assert "--single-select-options" in run.call_args_list[1].args[0]

def test_executor_requires_ui_repair_for_malformed_existing_field(tmp_path, monkeypatch):
    monkeypatch.setenv("BSP_PROJECT_REF","owner/7")
    with patch("subprocess.run",return_value=result({"fields":[{"name":"Role","options":[{"name":"rd"}]}]})):
        out=stage.executor(ctx(tmp_path))
    assert out["requires_input"] is True
    assert out["side_effects"] == []
