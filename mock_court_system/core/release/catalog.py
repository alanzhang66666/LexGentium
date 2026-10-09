"""Load release declarations and compare them with source-discovered routes."""
from __future__ import annotations

import ast
import fnmatch
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from .version import VERSION_ID

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE_ROOT = PROJECT_ROOT / "release"
_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
_TS_METHOD_RE = re.compile(
    r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b"
    r"|export\s+const\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b"
)


@dataclass(frozen=True, order=True)
class ActualRoute:
    surface: str
    method: str
    path: str


@dataclass(frozen=True)
class CatalogRoute:
    surface: str
    method: str
    path: str
    auth: str
    response_mode: str
    journey: str
    stability: str
    owner: str
    declaration_id: str


def _load_yaml(name: str, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    path = root / "release" / name
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported {name} schema version")
    if data.get("version") != VERSION_ID:
        raise ValueError(f"{name} version does not match {VERSION_ID}")
    return data


def load_route_catalog(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    catalog = _load_yaml("routes.yaml", root)
    for section in ("stable", "experimental"):
        if not isinstance(catalog.get(section), list):
            raise ValueError(f"routes.yaml {section} must be a list")
        for rule in catalog[section]:
            required = {"id", "surfaces", "methods", "path_patterns", "auth", "response_mode", "journey"}
            missing = sorted(required - set(rule))
            if missing:
                raise ValueError(f"route rule {rule.get('id', '<unknown>')} missing {missing}")
    return catalog


def load_configuration_catalog(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    catalog = _load_yaml("configuration.yaml", root)
    variables = catalog.get("variables")
    if not isinstance(variables, list):
        raise ValueError("configuration.yaml variables must be a list")
    names: set[str] = set()
    for variable in variables:
        required = {"name", "required", "profiles", "secret", "visibility", "owner"}
        missing = sorted(required - set(variable))
        if missing:
            raise ValueError(f"configuration variable missing {missing}")
        if variable["name"] in names:
            raise ValueError(f"duplicate configuration variable {variable['name']}")
        if variable["visibility"] not in {"browser_visible", "server_only"}:
            raise ValueError(f"invalid visibility for {variable['name']}")
        names.add(variable["name"])
    return catalog


def load_inventory(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    return _load_yaml("inventory.yaml", root)


def _literal_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def discover_fastapi_routes(root: Path = PROJECT_ROOT) -> set[ActualRoute]:
    routes: set[ActualRoute] = set()
    for source_path in sorted((root / "api" / "routers").glob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                method = decorator.func.attr.upper()
                if method not in _HTTP_METHODS or not decorator.args:
                    continue
                route_path = _literal_string(decorator.args[0])
                if route_path is not None:
                    routes.add(ActualRoute("fastapi", method, route_path))
    return routes


def _next_path(file_path: Path, app_root: Path) -> str:
    relative = file_path.parent.relative_to(app_root)
    parts = [part for part in relative.parts if not (part.startswith("(") and part.endswith(")"))]
    return "/" + "/".join(parts) if parts else "/"


def discover_next_routes(root: Path = PROJECT_ROOT) -> set[ActualRoute]:
    app_root = root / "app"
    routes: set[ActualRoute] = set()
    for route_file in sorted((app_root / "api").rglob("route.ts")):
        source = route_file.read_text(encoding="utf-8")
        for match in _TS_METHOD_RE.finditer(source):
            method = match.group(1) or match.group(2)
            routes.add(ActualRoute("next_bff", method, _next_path(route_file, app_root)))
    for page_file in sorted(app_root.rglob("page.tsx")):
        if "api" in page_file.relative_to(app_root).parts:
            continue
        routes.add(ActualRoute("next_page", "GET", _next_path(page_file, app_root)))
    return routes


def discover_actual_routes(root: Path = PROJECT_ROOT) -> set[ActualRoute]:
    return discover_fastapi_routes(root) | discover_next_routes(root)


def _rule_matches(route: ActualRoute, rule: dict[str, Any]) -> bool:
    return (
        route.surface in rule["surfaces"]
        and ("*" in rule["methods"] or route.method in rule["methods"])
        and any(fnmatch.fnmatchcase(route.path, pattern) for pattern in rule["path_patterns"])
    )


def _response_mode(route: ActualRoute, declared: str) -> str:
    if declared != "auto":
        return declared
    return "sse" if route.path.endswith("/stream") or route.path.endswith("/stream-round") else "json"


def build_route_diff(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    catalog = load_route_catalog(root)
    actual = discover_actual_routes(root)
    redirects = {(item["surface"], item["method"], item["path"]): item for item in catalog.get("redirects", [])}
    classified: dict[str, list[dict[str, Any]]] = {
        "stable": [], "experimental": [], "redirect": [], "excluded": []
    }
    unclassified: list[dict[str, str]] = []
    ambiguous: list[dict[str, Any]] = []

    for route in sorted(actual):
        exact_redirect = redirects.get((route.surface, route.method, route.path))
        matches: list[tuple[str, dict[str, Any]]] = []
        for section in ("stable", "experimental", "excluded"):
            for rule in catalog.get(section, []):
                if _rule_matches(route, rule):
                    matches.append((section, rule))
        if exact_redirect is not None:
            matches.append(("redirect", exact_redirect))
        if not matches:
            unclassified.append(asdict(route))
            continue
        if len(matches) != 1:
            ambiguous.append({"route": asdict(route), "matches": [m[1].get("id", m[0]) for m in matches]})
            continue
        section, rule = matches[0]
        if section in {"stable", "experimental"}:
            classified[section].append(asdict(CatalogRoute(
                surface=route.surface,
                method=route.method,
                path=route.path,
                auth=rule["auth"],
                response_mode=_response_mode(route, rule["response_mode"]),
                journey=rule["journey"],
                stability=section,
                owner=rule.get("owner", catalog.get("owner", "lexgentium")),
                declaration_id=rule["id"],
            )))
        else:
            classified[section].append({**asdict(route), **{k: v for k, v in rule.items() if k not in {"surfaces", "methods", "path_patterns"}}})

    actual_keys = {(route.surface, route.method, route.path) for route in actual}
    missing_redirects = [item for key, item in redirects.items() if key not in actual_keys]
    return {
        "version": VERSION_ID,
        "actual_count": len(actual),
        "classified": classified,
        "unclassified": unclassified,
        "ambiguous": ambiguous,
        "missing_redirects": missing_redirects,
        "is_clean": not unclassified and not ambiguous and not missing_redirects,
    }


def build_inventory_report(root: Path = PROJECT_ROOT) -> dict[str, Any]:
    inventory = load_inventory(root)
    status = inventory["authoritative_status"]
    status_path = root / status["path"]
    status_text = status_path.read_text(encoding="utf-8")
    missing_statements = [text for text in status["required_statements"] if text not in status_text]

    fixture_checks = []
    for fixture in inventory["research"]["technical_fixtures"]:
        fixture_checks.append({**fixture, "exists": (root / fixture["path"] / "pack.json").is_file()})

    candidate_checks = [
        {**pack, "exists": (root / pack["path"] / "pack.json").is_file()}
        for pack in inventory["research"].get("candidate_packs", [])
    ]

    split_files = inventory["civil_dataset"]["required_split_files"]
    data_root = root / inventory["civil_dataset"]["path"]
    missing_splits = sorted(name for name, filename in split_files.items() if not (data_root / filename).is_file())
    expected_missing = sorted(inventory["civil_dataset"]["expected_missing_splits"])

    return {
        "version": inventory["version"],
        "authoritative_status_path": status["path"],
        "authoritative_status_summary": status["summary"],
        "missing_authoritative_statements": missing_statements,
        "formal_pack_count": inventory["research"]["formal_pack_count"],
        "technical_fixtures": fixture_checks,
        "candidate_packs": candidate_checks,
        "unreviewed_annotations": inventory["research"]["unreviewed_annotations"],
        "case_25": inventory["research"]["case_25"],
        "missing_civil_splits": missing_splits,
        "expected_missing_civil_splits": expected_missing,
        "civil_split_inventory_matches": missing_splits == expected_missing,
        "observation_presentation": inventory["observation_presentation"],
        "is_consistent": (
            not missing_statements
            and inventory["research"]["formal_pack_count"] == 0
            and all(item["exists"] for item in fixture_checks)
            and all(item["exists"] for item in candidate_checks)
            and missing_splits == expected_missing
            and inventory["observation_presentation"]["gate_effect"] == "none"
        ),
    }


def version_surfaces(root: Path = PROJECT_ROOT) -> dict[str, str]:
    package_version = json.loads((root / "package.json").read_text(encoding="utf-8"))["version"]
    release_version = json.loads((root / "release" / "version.json").read_text(encoding="utf-8"))["version"]
    inventory_version = load_inventory(root)["version"]
    route_version = load_route_catalog(root)["version"]
    configuration_version = load_configuration_catalog(root)["version"]
    return {
        "package": package_version,
        "shared": VERSION_ID,
        "release": release_version,
        "routes": route_version,
        "configuration": configuration_version,
        "inventory": inventory_version,
    }


def all_versions_match(root: Path = PROJECT_ROOT) -> bool:
    return set(version_surfaces(root).values()) == {VERSION_ID}
