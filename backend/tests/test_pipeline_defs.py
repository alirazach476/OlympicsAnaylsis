"""The Dagster asset graph loads, is ordered Bronze -> Silver/Gold -> analytics -> validation, and the one-command runner lists the same stages."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dagster_definitions_load_with_expected_graph():
    from backend.pipeline.dagster_defs import defs
    keys = {a.key.to_user_string() for a in defs.assets}
    assert keys == {"bronze_inventory", "podium_results", "noc_registry", "silver_and_gold_marts", "analytics_results", "validation_report"}
    graph = defs.resolve_asset_graph() if hasattr(defs, "resolve_asset_graph") else defs.get_asset_graph()
    deps = {k.to_user_string(): {d.to_user_string() for d in graph.get(k).parent_keys} for k in graph.get_all_asset_keys()}
    assert deps["silver_and_gold_marts"] == {"noc_registry"} and deps["analytics_results"] == {"silver_and_gold_marts"}
    assert deps["validation_report"] == {"analytics_results"}


def test_runner_scripts_exist_for_every_stage():
    src = (ROOT / "scripts" / "run_pipeline.py").read_text(encoding="utf-8")
    scripts = re.findall(r'\("[a-z_]+", "([a-z_]+\.py)"\)', src)
    assert len(scripts) >= 20
    missing = [s for s in scripts if not (ROOT / "scripts" / s).exists()]
    assert missing == []


def test_dbt_project_has_models_and_tests():
    models = list((ROOT / "dbt" / "models").rglob("*.sql"))
    assert len(models) >= 6 and list((ROOT / "dbt" / "tests").glob("*.sql"))
