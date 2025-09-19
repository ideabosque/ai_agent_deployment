#!/usr/bin/env python3
"""
module_packager_recursive.py

Enhances dependency discovery for a target module/package with two complementary strategies:
  - "imports": Recursively crawl source files (AST) to find transitive imports and render an import-tree.
  - "metadata": Follow Requires-Dist from package metadata (pip-style) recursively and render a dependency tree.
  - "auto": Try metadata first; if it finds nothing, fall back to imports.

Adds:
  - "--inspect" to print resolved dependency sets and an ASCII tree (depending on strategy).
  - "--include-extras" to include optional extras in metadata resolution (replaces --additional-modules).

Usage examples:
  python module_packager_recursive.py requests /path/to/venv --inspect --strategy auto
  python module_packager_recursive.py requests /path/to/venv --strategy metadata --include-extras --output-dir dist
  python module_packager_recursive.py requests /path/to/venv --strategy imports  --inspect
"""

import argparse
import importlib
import importlib.metadata
import importlib.util
import logging
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

# Optional: robust parsing for "Requires-Dist" lines
try:
    from packaging.requirements import Requirement  # type: ignore
except Exception:  # lightweight fallback if "packaging" isn't installed

    class Requirement:  # minimal parser: name[; or ( or space] ...
        def __init__(self, req: str):
            req = req.strip()
            cut = len(req)
            for sep in [";", "(", " "]:
                if sep in req:
                    cut = min(cut, req.index(sep))
            self.name = req[:cut].strip()
            self.extras = set()
            self.marker = None


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ModulePackager:
    def __init__(self, venv_path: str):
        self.venv_path = Path(venv_path)
        self.site_packages = self._find_site_packages()
        self.dependencies: Set[str] = set()
        self.processed: Set[str] = set()
        self.external_deps: Set[str] = set()
        # For building an import tree when using AST strategy
        self.import_edges: Dict[str, Set[str]] = defaultdict(
            set
        )  # parent -> children (top-level names)

        self.excluded_modules = {
            # SilvaEngine Layer
            "boto3",
            "certifi",
            "lxml",
            "requests",
            "graphene",
            "pynamodb",
            "python-dotenv",
            "docutils",
            "wheel",
            "typing-extensions",
            "tenacity",
            "pymysql",
            "pyathena",
            "SQLAlchemy",
            "graphene_sqlalchemy",
            "graphene_sqlalchemy_filter",
            "zipp",
            "promise",
            "pendulum",
            "cerberus",
            "deepdiff",
            "pytz",
            "openpyxl",
            "python-jose",
            "chardet",
            "logzero",
            "phpserialize",
            "requests_oauthlib",
            "requests-toolbelt",
            "appdirs",
            "zeep",
            "oauthlib",
            "reportlab",
            "jinja2",
            "markupsafe",
            "pyhumps",
            "warlock",
            "xmltodict",
            "dicttoxml",
            "pandas",
            "jsonpickle",
            "elasticsearch",
            "hubspot-api-client",
            "sentry-sdk",
            "pydocparser",
            "pillow",
            "json2html",
            "levenshtein",
            "rapidfuzz",
            "click",
            "sshtunnel",
            "pypng",
            "qrcode",
            "cached-property",
            "pyyaml",
            "openai",
            "redis",
            "ujson",
            "pyarrow",
            "silvaengine_utility",
            "event_triggers",
            "silvaengine_base",
            "silvaengine_resource",
            "silvaengine_authorizer",
            "silvaengine_dynamodb_base",
            "event_recorder",
            "mutex_engine",
            # MCP Layer
            "ai_mcp_daemon_engine",
            "idna",
            "httpx",
            "annotated_types",
            "sniffio",
            "anyio",
            "typing_inspection",
            "pydantic",
            "pydantic_core",
            "mcp",
            "mcp-1.13.1.dist-info",
            "passlib",
            "httpx_sse",
            "pydantic_settings",
            "starlette",
            "sse_starlette",
            "humps",
            "shopify_connector",
            "shopify",
            "pyactiveresource",
            "jsonschema",
            "jsonschema_specifications",
            "attr",
            "attrs",
            "referencing",
            "rpds",
        }

    # ------------------------------
    # Environment discovery
    # ------------------------------
    def _find_site_packages(self) -> Path:
        """Find site-packages directory in venv"""
        possible_paths = [
            self.venv_path / "lib" / "python3.11" / "site-packages",
            self.venv_path / "lib" / "python3.10" / "site-packages",
            self.venv_path / "lib" / "python3.9" / "site-packages",
            self.venv_path / "Lib" / "site-packages",  # Windows
        ]
        for path in possible_paths:
            if path.exists():
                logger.info(f"Found site-packages at: {path}")
                return path
        raise ValueError(f"Could not find site-packages in {self.venv_path}")

    # ------------------------------
    # IMPORT (AST) STRATEGY
    # ------------------------------
    def find_module_dependencies(self, module_name: str):
        """Recursively find all dependencies for a module by walking its imports."""
        if module_name in self.processed:
            return
        self.processed.add(module_name)

        base_module = module_name.split(".")[0]
        is_excluded = base_module in self.excluded_modules
        if is_excluded:
            logger.info(
                f"Found excluded module (will skip in packaging): {module_name}"
            )
        else:
            logger.info(f"Processing dependency: {module_name}")

        try:
            module_path = self.site_packages / module_name
            if module_path.exists():
                if not is_excluded:
                    self.external_deps.add(module_name)
                if module_path.is_dir():
                    for py_file in module_path.rglob("*.py"):
                        if py_file.is_file():
                            self._parse_imports(py_file, module_name)
                else:
                    py_file = self.site_packages / f"{module_name}.py"
                    if py_file.exists():
                        self._parse_imports(py_file, module_name)
            else:
                try:
                    spec = importlib.util.find_spec(module_name)
                    if spec and spec.origin:
                        module_file = Path(spec.origin)
                        if str(self.site_packages) in str(module_file):
                            if not is_excluded:
                                self.external_deps.add(module_name)
                            self._parse_imports(module_file, module_name)
                        else:
                            logger.debug(
                                f"Skipping {module_name}: not in site-packages"
                            )
                except Exception as e:
                    logger.warning(f"Could not find or parse {module_name}: {e}")
        except Exception as e:
            logger.error(f"Error processing {module_name}: {e}")

    def _record_edge(self, parent: Optional[str], child: Optional[str]):
        if not parent or not child:
            return
        p = parent.split(".")[0]
        c = child.split(".")[0]
        if p != c:  # avoid self-edge
            self.import_edges[p].add(c)

    def _parse_imports(self, file_path: Path, current_module: Optional[str] = None):
        """Parse import statements from a Python file using AST and record edges."""
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            import ast

            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self._record_edge(current_module, alias.name)
                        self._check_module(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self._record_edge(current_module, node.module)
                        self._check_module(node.module)
                    elif node.level > 0 and current_module:
                        if node.level == 1:
                            if "." in current_module:
                                parent_module = ".".join(current_module.split(".")[:-1])
                                for alias in node.names:
                                    if alias.name != "*":
                                        full_name = (
                                            f"{parent_module}.{alias.name}"
                                            if parent_module
                                            else alias.name
                                        )
                                        self._record_edge(current_module, full_name)
                                        self._check_module(full_name)
                            else:
                                for alias in node.names:
                                    if alias.name != "*":
                                        self._record_edge(current_module, alias.name)
                                        self._check_module(alias.name)
                    if node.module:
                        for alias in node.names:
                            if alias.name != "*":
                                full_name = f"{node.module}.{alias.name}"
                                self._record_edge(current_module, full_name)
                                self._check_module(full_name)
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")

    def _check_module(self, module_name: str):
        """If module is in site-packages, queue it for recursive processing."""
        if not module_name or module_name in self.processed:
            return

        # Prefer Python's own stdlib listing when available (3.10+)
        try:
            stdlib_names = getattr(sys, "stdlib_module_names", set())
            if module_name.split(".")[0] in stdlib_names:
                return
        except Exception:
            pass

        # Static fallback list for older Pythons
        stdlib_modules = {
            "os",
            "sys",
            "json",
            "logging",
            "datetime",
            "time",
            "pathlib",
            "typing",
            "collections",
            "itertools",
            "functools",
            "re",
            "math",
            "random",
            "uuid",
            "hashlib",
            "base64",
            "urllib",
            "http",
            "email",
            "xml",
            "html",
            "csv",
            "sqlite3",
            "threading",
            "multiprocessing",
            "subprocess",
            "socket",
            "ssl",
            "gzip",
            "zipfile",
            "tarfile",
            "shutil",
            "tempfile",
            "glob",
            "fnmatch",
            "pickle",
            "copy",
            "weakref",
            "gc",
            "inspect",
            "ast",
            "dis",
            "traceback",
            "warnings",
            "contextlib",
            "abc",
            "enum",
            "dataclasses",
            "argparse",
            "configparser",
            "io",
            "struct",
            "array",
            "heapq",
            "bisect",
            "queue",
            "sched",
            "calendar",
            "decimal",
            "fractions",
            "statistics",
            "zoneinfo",
            "locale",
            "gettext",
            "codecs",
            "unicodedata",
            "stringprep",
            "readline",
            "rlcompleter",
            "cmd",
            "shlex",
            "platform",
            "errno",
            "ctypes",
            "mmap",
            "winreg",
            "msvcrt",
            "winsound",
            "posix",
            "pwd",
            "grp",
            "crypt",
            "termios",
            "tty",
            "pty",
            "fcntl",
            "resource",
            "nis",
            "syslog",
            "signal",
            "msilib",
            "distutils",
            "ensurepip",
            "venv",
            "zipapp",
            "pdb",
            "profile",
            "pstats",
            "timeit",
            "trace",
            "cProfile",
            "faulthandler",
            "tracemalloc",
        }
        if module_name in stdlib_modules:
            return

        parts = module_name.split(".")
        # Check for dependencies in site-packages
        for i in range(len(parts), 0, -1):
            partial = ".".join(parts[:i])
            ext_path = self.site_packages / partial
            if ext_path.exists():
                if partial not in self.processed:
                    self.find_module_dependencies(partial)
                return

        # Try common name variations
        base = parts[0]
        variations = [base, base.replace("_", "-"), base.replace("-", "_")]
        for v in variations:
            ext_path = self.site_packages / v
            if ext_path.exists() and v not in self.processed:
                self.find_module_dependencies(v)
                return

    # ------------------------------
    # METADATA STRATEGY
    # ------------------------------
    def _dist_top_levels(self, dist: importlib.metadata.Distribution) -> List[str]:
        """Return top-level importable names for a distribution (best-effort)."""
        try:
            files = list(dist.files or [])
            for f in files:
                if f.name.endswith("top_level.txt"):
                    txt = dist.read_text(str(f)) or ""
                    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
                    if lines:
                        return lines
        except Exception:
            pass
        name = (dist.metadata.get("Name") or "").strip()
        return [name.replace("-", "_")] if name else []

    def _normalize_req(self, req_str: str):
        """Parse a Requires-Dist entry into (name, extras, marker)."""
        try:
            r = Requirement(req_str)
            return (
                getattr(r, "name", None),
                getattr(r, "extras", set()),
                getattr(r, "marker", None),
            )
        except Exception:
            # very naive fallback: take token until first space/;/(
            s = req_str.strip()
            cut = len(s)
            for sep in [";", "(", " "]:
                if sep in s:
                    cut = min(cut, s.index(sep))
            return s[:cut], set(), None

    def build_metadata_graph(self, root_dist_name: str, include_extras: bool = False):
        """
        Recursively resolve Requires-Dist starting from a distribution name.
        Returns (dep_dists, dep_modules, tree):
          dep_dists: distribution names
          dep_modules: top-level module names
          tree: adjacency list mapping parent dist -> set(child dists)
        """
        seen: Set[str] = set()
        stack: List[str] = [root_dist_name]
        dep_dists: Set[str] = set()
        dep_modules: Set[str] = set()
        tree: Dict[str, Set[str]] = defaultdict(set)

        while stack:
            name = stack.pop()
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)

            try:
                dist = importlib.metadata.distribution(name)
            except importlib.metadata.PackageNotFoundError:
                logger.warning(f"Distribution not found: {name}")
                continue

            dist_name = dist.metadata.get("Name", name)
            dep_dists.add(dist_name)

            # Map distribution → top-level modules
            for top in self._dist_top_levels(dist):
                dep_modules.add(top)

            # Follow transitive requirements
            for req_str in dist.metadata.get_all("Requires-Dist") or []:
                rname, extras, marker = self._normalize_req(req_str)
                if not rname:
                    continue
                try:
                    if marker and hasattr(marker, "evaluate") and not marker.evaluate():
                        continue
                except Exception:
                    pass  # if packaging not present, ignore marker
                if extras and not include_extras:
                    continue
                tree[dist_name].add(rname)
                stack.append(rname)

        return dep_dists, dep_modules, tree

    def inspect_dependencies(
        self, module_or_dist: str, strategy: str = "auto", include_extras: bool = False
    ):
        """
        Compute recursive dependencies.
        strategy: 'imports' (AST), 'metadata' (Requires-Dist), or 'auto' (metadata then fallback).
        Returns (dep_modules, dep_dists, tree, tree_kind) where:
          - tree is an adjacency dict (dist graph for metadata, import graph for imports)
          - tree_kind in {"metadata", "imports", None}
        """
        dep_modules: Set[str] = set()
        dep_dists: Set[str] = set()
        tree_kind: Optional[str] = None

        if strategy in ("metadata", "auto"):
            try:
                d_dists, d_mods, d_tree = self.build_metadata_graph(
                    module_or_dist, include_extras=include_extras
                )
                if d_dists or d_mods:
                    dep_modules |= d_mods
                    dep_dists |= d_dists
                    tree_kind = "metadata"
                    return dep_modules, dep_dists, d_tree, tree_kind
            except Exception as e:
                logger.info(f"Metadata resolution failed for '{module_or_dist}': {e}")

        # Fallback to AST import walker
        self.external_deps.clear()
        self.processed.clear()
        self.import_edges.clear()
        self.find_module_dependencies(module_or_dist)
        dep_modules |= set(self.external_deps)
        tree_kind = "imports"

        # Best-effort: infer distributions for discovered modules
        try:
            for dist in importlib.metadata.distributions():
                tops = set(self._dist_top_levels(dist))
                if any(m.split(".")[0] in tops for m in dep_modules):
                    name = dist.metadata.get("Name", "")
                    if name:
                        dep_dists.add(name)
        except Exception:
            pass

        return dep_modules, dep_dists, self.import_edges, tree_kind

    # ------------------------------
    # FILE COLLECTION & PACKAGING
    # ------------------------------
    def collect_modules_by_names(self, module_names: Set[str]):
        """Collect files for a set of top-level module names (reuses existing rules)."""
        files_to_package: Dict[str, Path] = {}
        for dep in sorted(set(module_names)):
            base_dep = dep.split(".")[0]
            if base_dep in self.excluded_modules:
                logger.info(f"Skipping excluded dependency: {dep}")
                continue

            logger.info(f"Collecting files for dependency: {dep}")
            ext_path = self.site_packages / dep
            if ext_path.exists():
                if ext_path.is_dir():
                    for file_path in ext_path.rglob("*"):
                        if (
                            file_path.is_file()
                            and not file_path.name.startswith(".")
                            and not file_path.name.endswith(".pyc")
                        ):
                            try:
                                if (
                                    file_path.suffix in [".so", ".dll", ".dylib"]
                                    and file_path.stat().st_size > 50 * 1024 * 1024
                                ):
                                    continue
                            except Exception:
                                pass
                            rel_path = file_path.relative_to(
                                self.site_packages
                            ).as_posix()
                            files_to_package[rel_path] = file_path
                else:
                    py_file = self.site_packages / f"{dep}.py"
                    if py_file.exists():
                        files_to_package[f"{dep}.py"] = py_file
                    elif ext_path.suffix == ".py":
                        rel_path = ext_path.relative_to(self.site_packages).as_posix()
                        files_to_package[rel_path] = ext_path

            # Add matching *.dist-info / *.egg-info
            for info_dir in self.site_packages.glob(f"{dep}*"):
                if info_dir.is_dir() and (
                    info_dir.name.endswith(".dist-info")
                    or info_dir.name.endswith(".egg-info")
                ):
                    metadata_module = info_dir.name.split("-")[0].replace("_", "-")
                    if (
                        metadata_module in self.excluded_modules
                        or metadata_module.replace("-", "_") in self.excluded_modules
                    ):
                        continue
                    for file_path in info_dir.rglob("*"):
                        if file_path.is_file():
                            rel_path = file_path.relative_to(
                                self.site_packages
                            ).as_posix()
                            files_to_package[rel_path] = file_path

        logger.info(f"Total files to package: {len(files_to_package)}")
        return files_to_package

    def create_package(
        self,
        module_name: str,
        output_dir: Optional[Path] = None,
        include_extras: bool = False,
        strategy: str = "auto",
    ):
        """Create a ZIP package containing the module and all (recursively) resolved dependencies."""
        output_dir = Path(output_dir) if output_dir else Path.cwd()
        output_dir.mkdir(exist_ok=True, parents=True)

        # Resolve the recursive dependency set
        dep_modules, dep_dists, _tree, _kind = self.inspect_dependencies(
            module_name, strategy=strategy, include_extras=include_extras
        )

        if not dep_modules:
            logger.error(
                f"No dependencies found for '{module_name}' (strategy={strategy})"
            )
            return None

        # Collect files for all resolved top-level modules
        files_to_package = self.collect_modules_by_names(dep_modules)
        if not files_to_package:
            logger.error(f"No files gathered for '{module_name}' after collection.")
            return None

        zip_path = output_dir / f"{module_name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for archive_path, file_path in files_to_package.items():
                zipf.write(file_path, archive_path)
                logger.info(f"Added {archive_path} to package")

        logger.info(f"Package created: {zip_path}")
        logger.info(
            f"Resolved {len(dep_modules)} modules and {len(dep_dists)} distributions."
        )
        return zip_path

    # ------------------------------
    # TREE RENDERING (ASCII)
    # ------------------------------
    @staticmethod
    def _render_tree(adjacency: Dict[str, Set[str]], roots: Iterable[str]) -> str:
        """Render a clean ASCII tree from an adjacency list and a list of roots."""
        lines: List[str] = []

        def walk(node: str, prefix: str = "", is_last: bool = True):
            connector = "└─ " if is_last else "├─ "
            if prefix == "":
                lines.append(node)
            else:
                lines.append(prefix + connector + node)
            children = sorted(adjacency.get(node, []))
            for i, ch in enumerate(children):
                last = i == len(children) - 1
                new_prefix = prefix + ("   " if is_last else "│  ")
                walk(ch, new_prefix, last)

        for r in sorted(set(roots)):
            walk(r, "", True)
        return "".join(lines)


# ------------------------------
# CLI
# ------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Package Python modules with recursive dependency discovery (imports/metadata) and tree view"
    )
    parser.add_argument(
        "module", help="Module or distribution name to package/inspect (e.g., requests)"
    )
    parser.add_argument(
        "venv_path",
        help="Virtual environment path (e.g., /var/python3.11/silvaengine/env)",
    )
    parser.add_argument(
        "--output-dir", default=".", help="Output directory for ZIP file"
    )
    parser.add_argument(
        "--strategy",
        choices=["auto", "imports", "metadata"],
        default="auto",
        help="Dependency resolution strategy: 'imports' (AST), 'metadata' (Requires-Dist), or 'auto' (default)",
    )
    parser.add_argument(
        "--include-extras",
        action="store_true",
        help="Include optional extras from Requires-Dist during metadata resolution",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Only inspect the resolved dependency sets and print an ASCII tree (no zip)",
    )

    args = parser.parse_args()

    packager = ModulePackager(args.venv_path)

    if args.inspect:
        mods, dists, tree, kind = packager.inspect_dependencies(
            args.module, strategy=args.strategy, include_extras=args.include_extras
        )
        print("== Strategy Used ==", kind or "none")
        print("== Distributions ==")
        for d in sorted(dists):
            print(f" - {d}")
        print("== Top-level modules ==")
        for m in sorted(mods):
            print(f" - {m}")

        # Tree view
        print("== Dependency Tree ==")
        if kind == "metadata":
            # Build incoming count to find roots in the dist graph
            incoming: Dict[str, int] = defaultdict(int)
            for parent, kids in tree.items():
                for k in kids:
                    incoming[k] += 1
            # Prefer the provided name as a root; also include any with no incoming edges
            roots = [args.module]
            roots.extend(
                [n for n in tree.keys() if incoming.get(n, 0) == 0 and n not in roots]
            )
            ascii_tree = ModulePackager._render_tree(tree, roots)
            print(ascii_tree)
        elif kind == "imports":
            roots = [args.module.split(".")[0]]
            ascii_tree = ModulePackager._render_tree(tree, roots)
            print(ascii_tree)
        else:
            print("(no tree available)")
        return

    # Otherwise, produce zip
    zip_path = packager.create_package(
        args.module,
        Path(args.output_dir),
        include_extras=args.include_extras,
        strategy=args.strategy,
    )

    if zip_path:
        print(f"Successfully created package: {zip_path}")
    else:
        print("Failed to create package")
        sys.exit(1)


if __name__ == "__main__":
    main()
