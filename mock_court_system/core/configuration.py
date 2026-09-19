"""ConfigurationManager：profile、范围校验、immutable snapshot、原子更新（design §5）。

- ``APP_PROFILE`` = development|production|test；production 下必填变量、
  外部监听 token、数值范围必须有效，否则 readiness fail closed。
- ``ConfigurationSnapshot`` 不可变；操作接受时捕获 snapshot，运行中不读
  全局可变配置。更新走 validate → 连接测试 → 同目录临时文件 →
  flush/fsync → ``os.replace`` → fsync 父目录 → 新 identity → 锁内交换。
- Secret 公开视图一律固定 ``********``；fallback/空白/认证失败/timeout
  映射为 ``failed`` 或 ``degraded``，绝不映射 ``connected``。
"""
from __future__ import annotations

import ipaddress
import json
import os
import stat
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import yaml

from core.fingerprint import canonical_digest

SECRET_MASK = "********"
PROFILES = ("development", "production", "test")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_CATALOG_PATH = PROJECT_ROOT / "release" / "configuration.yaml"

#: 数值/枚举范围约束（生产与开发一致适用）
_RANGE_CONSTRAINTS: Dict[str, Tuple[float, float]] = {
    "LLM_TIMEOUT": (1, 600),
    "LLM_MAX_TOKENS": (1, 131072),
    "LLM_FAST_MAX_TOKENS": (1, 8192),
    "LLM_TEMPERATURE": (0, 2),
    "API_PORT": (1, 65535),
    "CI_MAX_AUTO_TURNS": (1, 100),
    "PLEAD_WINDOW_K": (1, 100),
    "HEARING_SUMMARY_WINDOW": (1, 200),
}
_FLAG_VARS = {"LLM_CACHE", "CI_USE_GRAPH", "PLEAD_USE_RUNTIME", "CI_LEGACY_ANALYSIS"}


class ConfigurationError(Exception):
    """配置校验失败；``issues`` 含变量名与稳定约束原因。"""

    def __init__(self, issues: List["ConfigIssue"]):
        self.issues = issues
        super().__init__(
            "invalid configuration: "
            + "; ".join(f"{i.name}:{i.reason}" for i in issues)
        )


@dataclass(frozen=True)
class ConfigIssue:
    name: str
    reason: str  # required | type | range | format | conflict
    constraint: str = ""


@dataclass(frozen=True)
class ConfigVariable:
    name: str
    required: bool
    profiles: Tuple[str, ...]
    secret: bool
    visibility: str  # server_only | browser_visible
    owner: str
    default: Optional[Any] = None


def load_variable_catalog(path: Path = CONFIG_CATALOG_PATH) -> Dict[str, ConfigVariable]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: Dict[str, ConfigVariable] = {}
    for row in data.get("variables") or []:
        out[row["name"]] = ConfigVariable(
            name=row["name"],
            required=bool(row.get("required", False)),
            profiles=tuple(row.get("profiles") or ()),
            secret=bool(row.get("secret", False)),
            visibility=str(row.get("visibility", "server_only")),
            owner=str(row.get("owner", "")),
            default=row.get("default"),
        )
    return out


def current_profile(env: Optional[Mapping[str, str]] = None) -> str:
    source = env if env is not None else os.environ
    profile = (source.get("APP_PROFILE") or "development").strip().lower()
    return profile if profile in PROFILES else "development"


def _is_loopback(host: str) -> bool:
    host = (host or "").strip().lower()
    if host in ("localhost", "127.0.0.1", "::1", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_candidate(
    values: Mapping[str, Any],
    *,
    profile: str,
    catalog: Optional[Dict[str, ConfigVariable]] = None,
) -> List[ConfigIssue]:
    """校验候选配置；返回 issue 列表（空 = 合法）。"""
    catalog = catalog or load_variable_catalog()
    issues: List[ConfigIssue] = []

    def _text(name: str) -> str:
        v = values.get(name)
        return "" if v is None else str(v).strip()

    # production 必填变量
    if profile == "production":
        for var in catalog.values():
            if var.required and profile in var.profiles and not _text(var.name):
                issues.append(ConfigIssue(var.name, "required", "required_in_production"))
        host = _text("API_HOST") or str(catalog.get("API_HOST", ConfigVariable("API_HOST", False, (), False, "", "")).default or "")
        if host and not _is_loopback(host) and not _text("API_TOKEN"):
            issues.append(
                ConfigIssue("API_TOKEN", "required", "external_listener_requires_token")
            )

    # 未声明变量拒绝
    for name in values:
        if name not in catalog:
            issues.append(ConfigIssue(name, "conflict", "undeclared_variable"))

    # 数值范围与 flag 类型
    for name, (lo, hi) in _RANGE_CONSTRAINTS.items():
        raw = _text(name)
        if not raw:
            continue
        try:
            num = float(raw)
        except ValueError:
            issues.append(ConfigIssue(name, "type", "number"))
            continue
        if not (lo <= num <= hi):
            issues.append(ConfigIssue(name, "range", f"{lo}..{hi}"))

    for name in _FLAG_VARS:
        raw = _text(name)
        if raw and raw not in ("0", "1", "true", "false"):
            issues.append(ConfigIssue(name, "format", "boolean_flag"))

    return issues


class ConnectionOutcome:
    """连接测试输入分类：不得把 fallback/empty/auth/timeout 当 connected。"""

    OK = "ok"
    EMPTY = "empty"
    FALLBACK = "fallback"
    AUTH_FAILURE = "auth_failure"
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"


def classify_connection(outcome: str) -> str:
    """返回 connected|degraded|failed；``ok`` 之外绝不返回 connected。"""
    if outcome == ConnectionOutcome.OK:
        return "connected"
    if outcome in (ConnectionOutcome.FALLBACK, ConnectionOutcome.UNREACHABLE):
        return "degraded"
    # empty / auth_failure / timeout / 未知：fail closed
    return "failed"


@dataclass(frozen=True)
class ConfigurationSnapshot:
    """不可变配置快照；操作接受时捕获。"""

    identity: str
    profile: str
    values: Mapping[str, Any]
    created_at: str

    def get(self, name: str, default: Any = None) -> Any:
        v = self.values.get(name)
        return default if v is None or str(v) == "" else v

    def public_view(
        self, catalog: Optional[Dict[str, ConfigVariable]] = None
    ) -> Dict[str, Any]:
        """脱敏视图：secret 固定 ``********``，不带任何明文。"""
        catalog = catalog or {}
        out: Dict[str, Any] = {}
        for name, value in self.values.items():
            var = catalog.get(name)
            if var and var.secret and str(value or "").strip():
                out[name] = SECRET_MASK
            else:
                out[name] = value
        return out

    def browser_view(
        self, catalog: Optional[Dict[str, ConfigVariable]] = None
    ) -> Dict[str, Any]:
        """浏览器可见视图：只含 browser_visible 非 secret 变量。"""
        catalog = catalog or {}
        return {
            name: value
            for name, value in self.values.items()
            if catalog.get(name)
            and catalog[name].visibility == "browser_visible"
            and not catalog[name].secret
        }


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _restrict_permissions(path: Path) -> None:
    """配置文件限服务账户读写（POSIX chmod 600；Windows 尽力而为）。"""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


class ConfigurationManager:
    """持有 active snapshot；update 原子替换，失败保留旧 identity/fingerprint。"""

    def __init__(
        self,
        persist_path: Optional[Path] = None,
        catalog: Optional[Dict[str, ConfigVariable]] = None,
        env: Optional[Mapping[str, str]] = None,
    ):
        self.catalog = catalog if catalog is not None else load_variable_catalog()
        self.persist_path = Path(persist_path) if persist_path else None
        self._lock = threading.Lock()
        self._snapshot = self._build_snapshot(env or dict(os.environ))

    def _build_snapshot(self, values: Mapping[str, Any]) -> ConfigurationSnapshot:
        declared = {
            name: values[name]
            for name in self.catalog
            if name in values and str(values[name]) != ""
        }
        return ConfigurationSnapshot(
            identity="cfg_" + canonical_digest(
                {"profile": current_profile(values), "values": declared}
            )[:24],
            profile=current_profile(values),
            values=declared,
            created_at=_utcnow_iso(),
        )

    def capture(self) -> ConfigurationSnapshot:
        """操作接受时捕获当前 snapshot。"""
        with self._lock:
            return self._snapshot

    @property
    def identity(self) -> str:
        return self.capture().identity

    def fingerprint(self) -> str:
        return self.capture().identity

    def validate(self, values: Mapping[str, Any], *, profile: Optional[str] = None) -> None:
        issues = validate_candidate(
            values, profile=profile or current_profile(), catalog=self.catalog
        )
        if issues:
            raise ConfigurationError(issues)

    def update(
        self,
        candidate: Mapping[str, Any],
        *,
        profile: Optional[str] = None,
        connection_outcome: Optional[str] = None,
    ) -> ConfigurationSnapshot:
        """原子更新：校验 → 连接分类 → temp+fsync+replace → 锁内换 snapshot。

        任一步失败抛错并保留旧 snapshot/identity。
        """
        eff_profile = profile or current_profile(candidate)
        self.validate(candidate, profile=eff_profile)
        if connection_outcome is not None and classify_connection(connection_outcome) == "failed":
            raise ConfigurationError(
                [ConfigIssue("connection", "conflict", "connection_test_failed")]
            )

        new_snapshot = self._build_snapshot({**candidate, "APP_PROFILE": eff_profile})

        if self.persist_path is not None:
            path = self.persist_path
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".cfg-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(
                        {"profile": eff_profile, "values": dict(candidate)},
                        fh,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    fh.flush()
                    os.fsync(fh.fileno())
                _restrict_permissions(Path(tmp_name))
                os.replace(tmp_name, path)
                _fsync_dir(path.parent)
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise

        with self._lock:
            self._snapshot = new_snapshot
        return new_snapshot
