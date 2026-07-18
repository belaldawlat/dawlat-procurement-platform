from __future__ import annotations

import argparse
import json
import py_compile
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable


class Severity(str, Enum):
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Finding:
    severity: Severity
    check: str
    message: str
    path: str | None = None
    line: int | None = None
    remediation: str = ""


EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules", "dist", "build",
}

REQUIRED_PATHS = (
    "app/main.py",
    "app/services/platform_bootstrap.py",
    "app/services/event_bus.py",
    "app/services/workflow_manager.py",
    "app/services/monitoring_service.py",
    "app/services/notification_service.py",
    "app/services/autonomous_procurement_orchestrator.py",
    "app/repositories/procurement_workflow_repository.py",
    "app/services/intelligence/risk_intelligence_engine.py",
    "app/services/intelligence/trust_intelligence_engine.py",
    "app/services/intelligence/explainable_ai_engine.py",
    "app/services/intelligence/learning_intelligence_engine.py",
    "app/services/intelligence/knowledge_graph_engine.py",
    "scripts/pre_release_security_check.py",
    "tests",
    "docs",
    "README.md",
    "requirements.txt",
    ".gitignore",
    ".env.example",
)

REQUIRED_GITIGNORE_RULES = (
    ".env",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "__pycache__/",
    ".venv/",
)

SECRET_PATTERNS = (
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("Tavily key", re.compile(r"\btvly-[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "Private key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "Possible hard-coded credential",
        re.compile(
            r"""(?ix)
            \b(api[_-]?key|secret|token|password|passwd)\b
            \s*[:=]\s*["']?([A-Za-z0-9_\-\/+=]{16,})
            """
        ),
    ),
)

PLACEHOLDER_WORDS = {
    "example", "placeholder", "dummy", "test", "changeme",
    "change-me", "your-key", "your_api_key", "your-secret",
    "not-set", "none",
}

SENSITIVE_GLOBS = (
    ".env",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "*credentials*.json",
    "*service_account*.json",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.bak",
    "*.backup",
    "*.dump",
    "*.zip",
    "*.7z",
)


class PreReleaseSecurityCheck:
    def __init__(self, root: Path, *, strict: bool = True) -> None:
        self.root = root.resolve()
        self.strict = strict
        self.findings: list[Finding] = []

    def run(self) -> list[Finding]:
        self.check_required_paths()
        self.check_gitignore()
        self.check_git_tracking()
        self.scan_secrets()
        self.compile_python()
        self.check_duplicate_modules()
        self.check_requirements()
        self.check_env_example()
        self.check_git_status()
        return self.findings

    def add(
        self,
        severity: Severity,
        check: str,
        message: str,
        *,
        path: Path | None = None,
        line: int | None = None,
        remediation: str = "",
    ) -> None:
        relative = None
        if path is not None:
            try:
                relative = str(path.resolve().relative_to(self.root))
            except Exception:
                relative = str(path)

        self.findings.append(
            Finding(
                severity=severity,
                check=check,
                message=message,
                path=relative,
                line=line,
                remediation=remediation,
            )
        )

    def files(self) -> Iterable[Path]:
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            yield path

    def python_files(self) -> Iterable[Path]:
        return (path for path in self.files() if path.suffix == ".py")

    def check_required_paths(self) -> None:
        for relative in REQUIRED_PATHS:
            path = self.root / relative
            if not path.exists():
                severity = (
                    Severity.CRITICAL
                    if relative.startswith("app/")
                    else Severity.HIGH
                )
                self.add(
                    severity,
                    "Required Paths",
                    f"Missing required path: {relative}",
                    path=path,
                    remediation="Restore it before creating a release tag.",
                )

    def check_gitignore(self) -> None:
        path = self.root / ".gitignore"
        if not path.exists():
            self.add(
                Severity.CRITICAL,
                "Git Ignore",
                ".gitignore is missing.",
                path=path,
                remediation="Create .gitignore before committing.",
            )
            return

        rules = {
            line.strip()
            for line in path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

        for required in REQUIRED_GITIGNORE_RULES:
            candidates = {
                required,
                "/" + required,
                required.rstrip("/"),
                "/" + required.rstrip("/"),
            }
            if not (rules & candidates):
                self.add(
                    Severity.CRITICAL,
                    "Git Ignore",
                    f"Missing ignore rule: {required}",
                    path=path,
                    remediation=f"Add `{required}` to .gitignore.",
                )

    def git(self, *args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

        return result.stdout if result.returncode == 0 else None

    def check_git_tracking(self) -> None:
        output = self.git("ls-files")
        if output is None:
            self.add(
                Severity.WARNING,
                "Git Tracking",
                "Could not inspect Git tracked files.",
            )
            return

        for relative in filter(None, map(str.strip, output.splitlines())):
            name = Path(relative).name
            if any(fnmatch(name.lower(), pattern.lower()) for pattern in SENSITIVE_GLOBS):
                self.add(
                    Severity.CRITICAL,
                    "Git Tracking",
                    f"Sensitive file is tracked by Git: {relative}",
                    path=self.root / relative,
                    remediation=(
                        "Remove it from tracking and rotate any exposed secret."
                    ),
                )

    def scan_secrets(self) -> None:
        for path in self.files():
            if path.name == ".env" or path.stat().st_size > 5_000_000:
                continue
            if path.suffix.lower() not in {
                ".py", ".md", ".txt", ".json", ".toml",
                ".yaml", ".yml", ".ini", ".cfg", ".ps1", ".sh",
            } and path.name not in {".gitignore", ".env.example"}:
                continue

            lines = path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()

            for number, line in enumerate(lines, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith(("#", "//", "*")):
                    continue

                for label, pattern in SECRET_PATTERNS:
                    match = pattern.search(line)
                    if not match:
                        continue
                    value = match.group(0).lower()
                    if any(word in value for word in PLACEHOLDER_WORDS):
                        continue
                    self.add(
                        Severity.CRITICAL,
                        "Secret Scan",
                        f"Possible {label} detected.",
                        path=path,
                        line=number,
                        remediation=(
                            "Remove and rotate the value; load it from .env "
                            "or a production secret manager."
                        ),
                    )

    def compile_python(self) -> None:
        for path in self.python_files():
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as error:
                self.add(
                    Severity.CRITICAL,
                    "Python Compile",
                    str(error),
                    path=path,
                    remediation="Fix the syntax error before release.",
                )

    def check_duplicate_modules(self) -> None:
        seen: dict[str, list[Path]] = {}
        for path in self.python_files():
            seen.setdefault(path.name.lower(), []).append(path)
            relative = path.relative_to(self.root)
            if "app" in relative.parts and "scripts" in relative.parts:
                self.add(
                    Severity.HIGH,
                    "Project Structure",
                    "Operational release script exists under app/.",
                    path=path,
                    remediation="Move it to the root scripts/ directory.",
                )

        for name, paths in seen.items():
            if name != "__init__.py" and len(paths) > 1:
                self.add(
                    Severity.WARNING,
                    "Duplicate Modules",
                    f"Duplicate Python filename `{name}` exists.",
                    path=paths[0],
                    remediation="Check for accidental copies or ambiguous imports.",
                )

    def check_requirements(self) -> None:
        path = self.root / "requirements.txt"
        if not path.exists():
            return

        lines = [
            line.strip()
            for line in path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        if not lines:
            self.add(
                Severity.HIGH,
                "Dependencies",
                "requirements.txt is empty.",
                path=path,
            )
            return

        counts: dict[str, int] = {}
        for line in lines:
            package = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].lower()
            counts[package] = counts.get(package, 0) + 1
            if "==" not in line:
                self.add(
                    Severity.WARNING,
                    "Dependencies",
                    f"Dependency is not pinned exactly: {line}",
                    path=path,
                )

        for package, count in counts.items():
            if count > 1:
                self.add(
                    Severity.HIGH,
                    "Dependencies",
                    f"Duplicate dependency entry: {package}",
                    path=path,
                )

    def check_env_example(self) -> None:
        example = self.root / ".env.example"
        env = self.root / ".env"
        if not example.exists():
            return

        def keys(path: Path) -> set[str]:
            if not path.exists():
                return set()
            result = set()
            for line in path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    result.add(stripped.split("=", 1)[0].strip())
            return result

        for key in sorted(keys(env) - keys(example)):
            self.add(
                Severity.WARNING,
                "Environment Template",
                f"`{key}` exists in .env but not .env.example.",
                path=example,
                remediation="Add the variable name with a safe placeholder.",
            )

        for number, line in enumerate(
            example.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines(),
            start=1,
        ):
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().lower()
            if value and not any(word in value for word in PLACEHOLDER_WORDS):
                self.add(
                    Severity.HIGH,
                    "Environment Template",
                    f".env.example may contain a real value for `{key.strip()}`.",
                    path=example,
                    line=number,
                    remediation="Replace it with a safe placeholder.",
                )

    def check_git_status(self) -> None:
        output = self.git("status", "--porcelain")
        if output is None:
            self.add(
                Severity.WARNING,
                "Git Status",
                "Could not inspect repository status.",
            )
        elif output.strip():
            self.add(
                Severity.HIGH if self.strict else Severity.WARNING,
                "Git Status",
                "Repository has uncommitted changes.",
                remediation=(
                    "Review, test and commit approved changes before freezing."
                ),
            )


def print_report(findings: list[Finding]) -> bool:
    blockers = [
        finding
        for finding in findings
        if finding.severity in {Severity.CRITICAL, Severity.HIGH}
    ]

    order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.WARNING: 2,
    }

    print("\n" + "=" * 72)
    print("DAWLAT ENTERPRISE PRE-RELEASE SECURITY CHECK")
    print("=" * 72)

    if not findings:
        print("PASS: No findings detected.")
    else:
        for finding in sorted(
            findings,
            key=lambda item: (
                order[item.severity],
                item.check,
                item.path or "",
                item.line or 0,
            ),
        ):
            location = ""
            if finding.path:
                location = f" [{finding.path}"
                if finding.line:
                    location += f":{finding.line}"
                location += "]"

            print(f"{finding.severity.value}: {finding.check}{location}")
            print(f"  {finding.message}")
            if finding.remediation:
                print(f"  Fix: {finding.remediation}")
            print()

    print("-" * 72)
    print(f"Critical/High blockers: {len(blockers)}")
    print(
        "RELEASE STATUS: PASSED"
        if not blockers
        else "RELEASE STATUS: BLOCKED"
    )
    print("=" * 72 + "\n")

    return not blockers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--non-strict", action="store_true")
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()

    checker = PreReleaseSecurityCheck(
        args.project_root,
        strict=not args.non_strict,
    )
    findings = checker.run()
    passed = print_report(findings)

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(
            json.dumps(
                {
                    "passed": passed,
                    "findings": [asdict(item) for item in findings],
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())