#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

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
import json
import logging
import os
import subprocess
import sys
import threading
import time
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


def slow_print(text: str, delay: float = 0.03):
    """Print text character by character with a delay."""
    for char in text:
        print(char, end="", flush=True)
        time.sleep(delay)
    print()  # Add newline at the end


class ModulePackager:
    def __init__(
        self,
        venv_path: Optional[str] = None,
        config_path: str = "mcp_packages.json",
        env_file: str = ".env",
    ):
        # Load configuration from JSON file
        self.config = self._load_config(config_path)

        # Load environment variables from .env file
        self._load_env_file(env_file)

        # Use venv_path from parameter or config file
        venv_path = venv_path or self.config.get("venv_path")
        if not venv_path:
            raise ValueError(
                "venv_path must be provided either as parameter or in config file"
            )

        self.venv_path = Path(venv_path)
        self.site_packages = self._find_site_packages()
        self.dependencies: Set[str] = set()
        self.processed: Set[str] = set()
        self.external_deps: Set[str] = set()
        # For building an import tree when using AST strategy
        self.import_edges: Dict[str, Set[str]] = defaultdict(
            set
        )  # parent -> children (top-level names)

        # Load excluded modules from config
        self.excluded_modules = set(self.config.get("excluded_modules", []))

    # ------------------------------
    # Configuration loading
    # ------------------------------
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file."""
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, "r") as f:
                    return json.load(f)
            else:
                logger.warning(f"Config file {config_path} not found, using defaults")
                return {}
        except Exception as e:
            logger.error(f"Error loading config file {config_path}: {e}")
            return {}

    def _load_env_file(self, env_path: str = ".env") -> None:
        """Load environment variables from .env file."""
        try:
            env_file = Path(env_path)
            if env_file.exists():
                with open(env_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            # Remove inline comments and clean up value
                            if "#" in value:
                                value = value.split("#")[0]
                            value = value.strip().strip('"').strip("'")
                            if value:  # Only set non-empty values
                                os.environ[key] = value
                logger.info(f"Loaded environment variables from {env_path}")
            else:
                logger.info(
                    f"No .env file found at {env_path}, using existing environment variables"
                )
        except Exception as e:
            logger.warning(f"Error loading .env file {env_path}: {e}")

    def get_module_extras(self, module_name: str) -> List[str]:
        """Get include_extras for a specific module from config."""
        modules_config = self.config.get("modules", {})
        module_config = modules_config.get(module_name, {})
        return module_config.get("include_extras", [])

    def _show_progress_indicator(
        self, stop_event: threading.Event, file_size_mb: float
    ):
        """Show a progress indicator while upload is happening."""
        # Wait a moment for the initial log message to complete
        time.sleep(0.5)

        spinner_chars = "|/-\\"
        spinner_idx = 0
        start_time = time.time()

        while not stop_event.is_set():
            elapsed = time.time() - start_time
            char = spinner_chars[spinner_idx % len(spinner_chars)]
            print(
                f"\r{char} Uploading {file_size_mb:.1f}MB to S3... ({elapsed:.1f}s)",
                end="",
                flush=True,
            )
            spinner_idx += 1
            time.sleep(0.1)

    def sync_to_s3(self, zip_path: Path) -> bool:
        """Sync the ZIP file to S3 using AWS CLI with all settings from .env file."""
        # Get all AWS settings from environment variables (loaded from .env)
        aws_access_key_id = os.environ.get("aws_access_key_id")
        aws_secret_access_key = os.environ.get("aws_secret_access_key")
        bucket = os.environ.get("mcp_bucket")
        region = os.environ.get("region_name")

        # Validate required settings
        if not bucket:
            logger.error(f"No bucket specified. Set mcp_bucket in environment file.")
            return False

        if not aws_access_key_id or not aws_secret_access_key:
            logger.error(
                f"AWS credentials not found. Set aws_access_key_id and aws_secret_access_key in environment file."
            )
            return False

        # Get file size for progress indicator
        file_size_bytes = zip_path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        # Construct S3 path (directly use zip file name without prefix)
        s3_uri = f"s3://{bucket}/{zip_path.name}"

        # Build AWS CLI command
        cmd = ["aws", "s3", "cp", str(zip_path), s3_uri]

        if region:
            cmd.extend(["--region", region])

        # Set up environment with AWS credentials (AWS CLI expects uppercase)
        env = dict(os.environ)
        env["AWS_ACCESS_KEY_ID"] = aws_access_key_id
        env["AWS_SECRET_ACCESS_KEY"] = aws_secret_access_key
        logger.info(
            f"Using AWS settings from environment file (bucket: {bucket}, region: {region})"
        )

        # Start progress indicator
        stop_event = threading.Event()
        progress_thread = threading.Thread(
            target=self._show_progress_indicator, args=(stop_event, file_size_mb)
        )
        progress_thread.daemon = True
        progress_thread.start()

        try:
            logger.info(
                f"Syncing {zip_path.name} ({file_size_mb:.1f}MB) to {s3_uri}..."
            )
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, env=env
            )

            # Stop progress indicator
            stop_event.set()
            progress_thread.join(timeout=1.0)
            print(
                f"\r✓ Successfully uploaded {file_size_mb:.1f}MB to S3: {s3_uri}"
                + " " * 20
            )
            print()  # Add newline for clean output

            logger.info(f"Successfully synced to S3: {s3_uri}")
            return True
        except subprocess.CalledProcessError as e:
            # Stop progress indicator
            stop_event.set()
            progress_thread.join(timeout=1.0)
            print(f"\r✗ Upload failed" + " " * 50)
            print()  # Add newline for clean output

            logger.error(f"Failed to sync to S3: {e.stderr}")
            return False
        except FileNotFoundError:
            # Stop progress indicator
            stop_event.set()
            progress_thread.join(timeout=1.0)
            print(f"\r✗ AWS CLI not found" + " " * 50)
            print()  # Add newline for clean output

            logger.error(
                "AWS CLI not found. Please install AWS CLI to use S3 sync functionality."
            )
            return False

    # ------------------------------
    # Environment discovery
    # ------------------------------
    def _find_site_packages(self) -> Path:
        """Find site-packages directory in venv"""
        possible_paths = [
            self.venv_path / "lib" / "python3.12" / "site-packages",
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

        # Check if module or any of its parent modules are excluded
        module_parts = module_name.split(".")
        is_excluded = False
        for i in range(1, len(module_parts) + 1):
            parent_module = ".".join(module_parts[:i])
            if parent_module in self.excluded_modules:
                is_excluded = True
                logger.info(
                    f"Found excluded module (will skip in packaging): {module_name} (parent {parent_module} is excluded)"
                )
                break

        if not is_excluded:
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

        # Check if module or any of its parent modules are excluded
        module_parts = module_name.split(".")
        for i in range(1, len(module_parts) + 1):
            parent_module = ".".join(module_parts[:i])

            # Check against excluded modules
            if parent_module in self.excluded_modules:
                logger.debug(
                    f"Skipping {module_name}: parent {parent_module} is excluded"
                )
                return

        # Prefer Python's own stdlib listing when available (3.10+)
        try:
            stdlib_names = getattr(sys, "stdlib_module_names", set())
            # Check if any parent module is in stdlib
            for i in range(1, len(module_parts) + 1):
                parent_module = ".".join(module_parts[:i])
                if parent_module in stdlib_names:
                    logger.debug(
                        f"Skipping {module_name}: parent {parent_module} is stdlib"
                    )
                    return
        except Exception:
            pass

        # Load stdlib modules from config
        stdlib_modules = set(self.config.get("stdlib_modules", []))
        # Check if any parent module is in stdlib (fallback)
        for i in range(1, len(module_parts) + 1):
            parent_module = ".".join(module_parts[:i])
            if parent_module in stdlib_modules:
                logger.debug(
                    f"Skipping {module_name}: parent {parent_module} is stdlib (fallback)"
                )
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
        self,
        module_or_dist: str,
        strategy: str = "auto",
        include_extras: bool = False,
        extra_modules: List[str] = None,
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

        # Add module-specific extras from config
        config_extras = self.get_module_extras(module_or_dist)
        if config_extras:
            logger.info(
                f"Adding config extras for {module_or_dist}: {', '.join(config_extras)}"
            )
            dep_modules.update(config_extras)

        # Add extra modules to the dependency set
        if extra_modules:
            logger.info(
                f"Adding extra modules to dependencies: {', '.join(extra_modules)}"
            )
            dep_modules.update(extra_modules)

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
            # Check if module or any of its parent modules are excluded
            module_parts = dep.split(".")
            is_excluded = False
            for i in range(1, len(module_parts) + 1):
                parent_module = ".".join(module_parts[:i])
                if parent_module in self.excluded_modules:
                    is_excluded = True
                    logger.info(
                        f"Skipping excluded dependency: {dep} (parent {parent_module} is excluded)"
                    )
                    break

            if is_excluded:
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
        extra_modules: List[str] = None,
        env_file_provided: bool = False,
    ):
        """Create a ZIP package containing the module and all (recursively) resolved dependencies."""
        output_dir = Path(output_dir) if output_dir else Path.cwd()
        output_dir.mkdir(exist_ok=True, parents=True)

        # Resolve the recursive dependency set
        dep_modules, dep_dists, _tree, _kind = self.inspect_dependencies(
            module_name,
            strategy=strategy,
            include_extras=include_extras,
            extra_modules=extra_modules,
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

        # Sync to S3 if environment file provided
        if env_file_provided:
            sync_success = self.sync_to_s3(zip_path)
            if not sync_success:
                logger.warning(f"Package created locally but failed to sync to S3")

        return zip_path

    # ------------------------------
    # TREE RENDERING (ASCII)
    # ------------------------------
    @staticmethod
    def _render_tree(adjacency: Dict[str, Set[str]], roots: Iterable[str]) -> str:
        """Render a clean ASCII tree with proper Unicode box-drawing characters."""
        lines: List[str] = []
        visited_in_path: Set[str] = set()  # Track current path to detect cycles
        global_visited: Set[str] = set()  # Track all visited to avoid duplicates

        def walk(node: str, prefix: str = "", is_last: bool = True, depth: int = 0):
            # Detect circular dependencies
            if node in visited_in_path:
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{node} ↻ (circular)\n")
                return

            # Add current node to path
            visited_in_path.add(node)

            # Choose the right connector and display the node
            if depth == 0:
                # Root node
                lines.append(f"{node}\n")
            else:
                connector = "└── " if is_last else "├── "
                # Mark if we've seen this node before (but not in current path)
                marker = " (already shown)" if node in global_visited else ""
                lines.append(f"{prefix}{connector}{node}{marker}\n")

            # Get children and sort them
            children = sorted(adjacency.get(node, set()))

            # Only show children if we haven't fully processed this node before
            show_children = node not in global_visited
            if show_children:
                # Mark as globally visited before processing children
                global_visited.add(node)

                for i, child in enumerate(children):
                    is_last_child = i == len(children) - 1

                    # Build the prefix for the child
                    if depth == 0:
                        child_prefix = ""
                    else:
                        child_prefix = prefix + ("    " if is_last else "│   ")

                    walk(child, child_prefix, is_last_child, depth + 1)

            # Remove from current path when backtracking
            visited_in_path.discard(node)

        # Process each root
        roots_list = sorted(set(roots))
        for i, root in enumerate(roots_list):
            visited_in_path.clear()
            walk(root, "", True, 0)

            # Add spacing between different root trees
            if i < len(roots_list) - 1:
                lines.append("\n")

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
        "--venv-path",
        default="/var/python3.12/silvaengine/env",
        help="Virtual environment path (e.g., /var/python3.12/silvaengine/env). If not provided, will use path from config file.",
    )
    parser.add_argument(
        "--config",
        default="mcp_packages.json",
        help="Path to configuration JSON file (default: mcp_packages.json)",
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
        type=str,
        default="",
        help="Comma-separated list of additional modules to include in packaging (e.g., 'module1,module2,module3')",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Only inspect the resolved dependency sets and print an ASCII tree (no zip)",
    )
    parser.add_argument(
        "--slow-print",
        type=float,
        default=0.0,
        metavar="DELAY",
        help="Enable slow character-by-character printing with specified delay in seconds (e.g., 0.03)",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to environment file containing AWS settings (default: .env)",
    )

    args = parser.parse_args()

    # Parse include-extras as a list of modules
    include_extras_list = []
    if args.include_extras:
        include_extras_list = [
            module.strip()
            for module in args.include_extras.split(",")
            if module.strip()
        ]

    # Set up print function based on slow-print option
    if args.slow_print > 0:

        def print_func(text: str):
            slow_print(text, args.slow_print)

    else:
        print_func = print

    packager = ModulePackager(
        getattr(args, "venv_path", None), args.config, getattr(args, "env_file", ".env")
    )

    if args.inspect:
        mods, dists, tree, kind = packager.inspect_dependencies(
            args.module,
            strategy=args.strategy,
            include_extras=False,
            extra_modules=include_extras_list,
        )
        print_func("=" * 60)
        print_func(f"DEPENDENCY ANALYSIS FOR: {args.module}")
        print_func("=" * 60)
        print_func(f"Strategy Used: {kind or 'none'}")
        print_func(f"Total Distributions: {len(dists)}")
        print_func(f"Total Top-level Modules: {len(mods)}")
        if include_extras_list:
            print_func(
                f"Extra Modules Included: {len(include_extras_list)} ({', '.join(include_extras_list)})"
            )
        print_func("")

        if dists:
            print_func("📦 DISTRIBUTIONS:")
            for d in sorted(dists):
                print_func(f"  • {d}")
            print_func("")

        if mods:
            print_func("🐍 TOP-LEVEL MODULES:")
            for m in sorted(mods):
                print_func(f"  • {m}")
            print_func("")

        # Tree view
        print_func("🌳 DEPENDENCY TREE:")
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
            print_func(ascii_tree)
        elif kind == "imports":
            # For imports strategy, find actual roots (modules with no incoming dependencies)
            incoming: Dict[str, int] = defaultdict(int)
            for parent, children in tree.items():
                for child in children:
                    incoming[child] += 1

            # Find all modules that are not imported by others (potential roots)
            all_modules = (
                set(tree.keys()) | set().union(*tree.values()) if tree else set()
            )
            actual_roots = [m for m in all_modules if incoming.get(m, 0) == 0]

            # If no clear roots found or if the target module exists, include it
            target_root = args.module.split(".")[0]
            if not actual_roots or target_root in all_modules:
                if target_root not in actual_roots:
                    actual_roots = [target_root] + actual_roots

            if actual_roots and tree:
                ascii_tree = ModulePackager._render_tree(tree, actual_roots)
                print_func(ascii_tree)
            else:
                print_func(f"No import dependencies found for '{args.module}'")
        else:
            print_func("(no tree available)")
        return

    # Otherwise, produce zip
    env_file_provided = hasattr(args, "env_file")  # and args.env_file != ".env"
    zip_path = packager.create_package(
        args.module,
        Path(args.output_dir),
        include_extras=False,
        strategy=args.strategy,
        extra_modules=include_extras_list,
        env_file_provided=env_file_provided,
    )

    if zip_path:
        print(f"Successfully created package: {zip_path}")
    else:
        print("Failed to create package")
        sys.exit(1)


if __name__ == "__main__":
    main()
