"""Convert stored legacy risks into the public generic risk envelope."""
from copy import deepcopy
from typing import Any


def _legacy_steps(plan: dict[str, Any]) -> list[dict[str, Any]]:
    steps = []
    for item in plan.get("steps", []) or []:
        if isinstance(item, dict):
            converted = deepcopy(item)
            converted.pop("step", None)
            converted.setdefault("data", {})
            steps.append(converted)
    return steps


def normalize_risk_document(document: dict[str, Any]) -> dict[str, Any]:
    """Return a new generic document without mutating MongoDB source data."""
    source = deepcopy(document)
    vessel = source.get("vessel") if isinstance(source.get("vessel"), dict) else {}
    entity = source.get("entity") if isinstance(source.get("entity"), dict) else None
    if entity is None:
        entity = {
            "type": "vessel" if vessel else "unknown",
            "id": vessel.get("id", ""),
            "name": vessel.get("name", ""),
            "data": {},
        }
    else:
        entity = deepcopy(entity)
        entity.setdefault("data", {})

    details = source.get("details") if isinstance(source.get("details"), dict) else {}
    detail_sections = deepcopy(details.get("sections", []))
    if "sections" not in details:
        for key, title in (("underlyingExposure", "Underlying Exposure"), ("impact", "Impact")):
            items = details.get(key, [])
            if items:
                detail_sections.append({"type": "bullets", "title": title, "items": deepcopy(items)})

    mitigation = source.get("mitigation") if isinstance(source.get("mitigation"), dict) else None
    if mitigation is not None:
        mitigation_sections = deepcopy(mitigation.get("sections", []))
    else:
        plan = source.get("mitigationPlan") if isinstance(source.get("mitigationPlan"), dict) else {}
        mitigation_sections = []
        if plan.get("summary"):
            mitigation_sections.append({"type": "text", "title": "Summary", "content": plan["summary"]})
        steps = _legacy_steps(plan)
        if steps:
            mitigation_sections.append({"type": "steps", "title": "Action Plan", "items": steps})
        if plan.get("lastUpdated"):
            mitigation_sections.append({
                "type": "callout", "title": "Last Updated", "content": plan["lastUpdated"]
            })

    extensions = deepcopy(source.get("extensions", {}))
    legacy_adapter = {
        key: deepcopy(source[key])
        for key in ("deadline", "fundingShortfall", "paymentsAtRisk", "accountRisk")
        if key in source
    }
    if legacy_adapter:
        extensions.setdefault("legacy", {}).update(legacy_adapter)

    return {
        "riskId": source["riskId"],
        "accountId": source["accountId"],
        "title": source["title"],
        "severity": source["severity"],
        "status": source.get("status", "open"),
        "summary": source.get("summary"),
        "entity": entity,
        "metrics": deepcopy(source.get("metrics", [])),
        "details": {"sections": detail_sections},
        "mitigation": {"sections": mitigation_sections},
        "metadata": deepcopy(source.get("metadata", {})),
        "extensions": extensions,
        "tracking": deepcopy(source.get("tracking", {})),
        "assignment": deepcopy(source.get("assignment", {})),
        "createdAt": source["createdAt"],
        "updatedAt": source["updatedAt"],
    }
