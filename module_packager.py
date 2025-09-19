#!/usr/bin/env python3
import argparse
import importlib
import importlib.util
import logging
import os
import pkgutil
import sys
import zipfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ModulePackager:
    def __init__(self, venv_path):
        self.venv_path = Path(venv_path)
        self.site_packages = self._find_site_packages()
        self.dependencies = set()
        self.processed = set()
        self.external_deps = set()

    def _find_site_packages(self):
        """Find site-packages directory in venv"""
        # Look for site-packages in common locations
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

    def find_module_dependencies(self, module_name):
        """Recursively find all dependencies for a module"""
        if module_name in self.processed:
            return

        self.processed.add(module_name)

        try:
            # Look for module in site_packages
            module_path = self.site_packages / module_name

            if module_path.exists():
                self.external_deps.add(module_name)
                logger.info(f"Added dependency: {module_name}")

                # Parse all Python files in the module
                if module_path.is_dir():
                    # Parse all Python files in the package
                    for py_file in module_path.rglob("*.py"):
                        if py_file.is_file():
                            logger.debug(f"Parsing imports from {py_file}")
                            self._parse_imports(py_file, module_name)
                else:
                    # Check if there's a .py file with this name
                    py_file = self.site_packages / f"{module_name}.py"
                    if py_file.exists():
                        logger.debug(f"Parsing imports from {py_file}")
                        self._parse_imports(py_file, module_name)
            else:
                # Try to use importlib as fallback
                try:
                    spec = importlib.util.find_spec(module_name)
                    if spec and spec.origin:
                        module_file = Path(spec.origin)
                        # Only process if it's in site_packages
                        if str(self.site_packages) in str(module_file):
                            self.external_deps.add(module_name)
                            logger.info(
                                f"Added dependency via importlib: {module_name}"
                            )
                            logger.debug(
                                f"Parsing imports from {module_file} (via importlib)"
                            )
                            self._parse_imports(module_file, module_name)
                        else:
                            logger.debug(
                                f"Skipping {module_name}: not in site_packages"
                            )
                except Exception as e:
                    logger.warning(f"Could not find or parse {module_name}: {e}")

        except Exception as e:
            logger.error(f"Error processing {module_name}: {e}")

    def _parse_imports(self, file_path, current_module=None):
        """Parse import statements from a Python file"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            import ast

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self._check_module(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        # Handle absolute imports
                        self._check_module(node.module)
                    elif node.level > 0 and current_module:
                        # Handle relative imports (from . import, from .. import)
                        if node.level == 1:
                            # Same package relative import
                            if "." in current_module:
                                parent_module = ".".join(current_module.split(".")[:-1])
                                for alias in node.names:
                                    if alias.name != "*":
                                        full_name = (
                                            f"{parent_module}.{alias.name}"
                                            if parent_module
                                            else alias.name
                                        )
                                        self._check_module(full_name)
                            else:
                                for alias in node.names:
                                    if alias.name != "*":
                                        self._check_module(alias.name)
                        # Could add more levels if needed
                    # Also check imported names for ImportFrom
                    if node.module:
                        for alias in node.names:
                            if alias.name != "*":
                                full_import_name = f"{node.module}.{alias.name}"
                                self._check_module(full_import_name)

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")

    def _check_module(self, module_name):
        """Check if module is in site_packages and add to dependencies"""
        if not module_name or module_name in self.processed:
            return

        # Skip standard library modules
        stdlib_modules = [
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
        ]
        if module_name in stdlib_modules:
            return

        # Split module name to check parent modules
        parts = module_name.split(".")

        # Check for dependencies in site-packages
        for i in range(len(parts), 0, -1):
            partial_name = ".".join(parts[:i])
            ext_path = self.site_packages / partial_name

            if ext_path.exists():
                if partial_name not in self.external_deps:
                    self.external_deps.add(partial_name)
                    logger.info(f"Found dependency: {partial_name}")
                    self._find_external_dependencies(partial_name)
                return

        # Check for common package name variations
        base_name = parts[0]
        variations = [
            base_name,
            base_name.replace("_", "-"),
            base_name.replace("-", "_"),
        ]

        for variation in variations:
            # Check in site-packages
            ext_path = self.site_packages / variation
            if ext_path.exists() and variation not in self.external_deps:
                self.external_deps.add(variation)
                logger.info(f"Found dependency variation: {variation}")
                self._find_external_dependencies(variation)
                return

    def _find_external_dependencies(self, module_name):
        """Find dependencies of external modules - simplified to avoid infinite recursion"""
        if module_name in self.processed:
            return

        self.processed.add(module_name)

        try:
            ext_path = self.site_packages / module_name
            if ext_path.is_dir():
                # Only parse top-level __init__.py to avoid deep recursion
                init_file = ext_path / "__init__.py"
                if init_file.exists():
                    self._parse_imports(init_file, module_name)

            # Also check for related packages (e.g., package-version.dist-info)
            for related in self.site_packages.glob(f"{module_name}*"):
                if related.is_dir() and related.name != module_name:
                    if related.name.endswith(".dist-info") or related.name.endswith(
                        ".egg-info"
                    ):
                        continue
                    # Check if it's a valid Python package name (avoid version suffixes)
                    if "-" not in related.name or related.name.replace(
                        "-", "_"
                    ) == module_name.replace("-", "_"):
                        if related.name not in self.external_deps:
                            self.external_deps.add(related.name)
                            logger.info(
                                f"Found related external dependency: {related.name}"
                            )

        except Exception as e:
            logger.warning(
                f"Error finding dependencies for external module {module_name}: {e}"
            )

    def collect_module_files(self, module_name):
        """Collect all files for a module and its dependencies"""
        files_to_package = {}

        # First, find all dependencies
        self.find_module_dependencies(module_name)

        logger.info(
            f"Found {len(self.external_deps)} dependencies: {self.external_deps}"
        )

        if len(self.external_deps) == 0:
            logger.warning(
                "No dependencies found! This might indicate an issue with dependency detection."
            )
            logger.info(f"Site packages: {self.site_packages}")
            logger.info(f"Current working directory: {Path.cwd()}")
            # Check if the target module itself exists
            target_path = self.site_packages / module_name
            if not target_path.exists():
                logger.error(
                    f"Target module '{module_name}' not found at {target_path}"
                )
                logger.info("Available modules in site-packages:")
                for item in self.site_packages.iterdir():
                    if (
                        item.is_dir()
                        and not item.name.startswith(".")
                        and not item.name.endswith((".dist-info", ".egg-info"))
                    ):
                        logger.info(f"  - {item.name}")

        # Collect all dependencies from site-packages
        for dep in self.external_deps:
            logger.info(f"Collecting files for dependency: {dep}")
            ext_path = self.site_packages / dep
            if ext_path.exists():
                if ext_path.is_dir():
                    file_count = 0
                    for file_path in ext_path.rglob("*"):
                        if (
                            file_path.is_file()
                            and not file_path.name.startswith(".")
                            and not file_path.name.endswith(".pyc")
                        ):
                            # Skip large unnecessary files
                            if (
                                file_path.suffix in [".so", ".dll", ".dylib"]
                                and file_path.stat().st_size > 50 * 1024 * 1024
                            ):  # Skip files > 50MB
                                logger.debug(f"Skipping large binary file: {file_path}")
                                continue
                            # Place dependencies directly at root level
                            rel_path = file_path.relative_to(
                                self.site_packages
                            ).as_posix()
                            files_to_package[rel_path] = file_path
                            file_count += 1
                            logger.debug(f"Adding file: {rel_path}")
                    logger.info(f"Added {file_count} files from package: {dep}")
                else:
                    # Handle single file module or check if there's a .py file with this name
                    py_file = self.site_packages / f"{dep}.py"
                    if py_file.exists():
                        rel_path = f"{dep}.py"
                        files_to_package[rel_path] = py_file
                        logger.info(f"Added file: {rel_path}")
                    elif ext_path.suffix == ".py":
                        rel_path = ext_path.relative_to(self.site_packages).as_posix()
                        files_to_package[rel_path] = ext_path
                        logger.info(f"Added file: {rel_path}")

            # Also include corresponding .dist-info/.egg-info for this dependency
            for info_dir in self.site_packages.glob(f"{dep}*"):
                if info_dir.is_dir() and (
                    info_dir.name.endswith(".dist-info")
                    or info_dir.name.endswith(".egg-info")
                ):
                    for file_path in info_dir.rglob("*"):
                        if file_path.is_file():
                            # Place metadata files directly at root level
                            rel_path = file_path.relative_to(
                                self.site_packages
                            ).as_posix()
                            files_to_package[rel_path] = file_path
                            logger.debug(f"Adding metadata file: {rel_path}")

        logger.info(f"Total files to package: {len(files_to_package)}")
        return files_to_package

    def create_package(self, module_name, output_dir=None, additional_modules=None):
        """Create a ZIP package containing the module and all dependencies"""
        if not output_dir:
            output_dir = Path.cwd()
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(exist_ok=True)

        # Collect all files for main module
        files_to_package = self.collect_module_files(module_name)

        # Process additional modules if provided
        if additional_modules:
            for additional_module in additional_modules:
                logger.info(f"Processing additional module: {additional_module}")
                # Reset the state for each additional module to ensure clean processing
                additional_packager = ModulePackager(self.venv_path)
                additional_files = additional_packager.collect_module_files(
                    additional_module
                )

                # Merge files, with additional modules taking precedence if there are conflicts
                for archive_path, file_path in additional_files.items():
                    if archive_path in files_to_package:
                        logger.warning(
                            f"File conflict: {archive_path} already exists, overwriting with version from {additional_module}"
                        )
                    files_to_package[archive_path] = file_path

        if not files_to_package:
            logger.error(f"No files found for module {module_name}")
            return None

        # Create ZIP file
        zip_path = output_dir / f"{module_name}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for archive_path, file_path in files_to_package.items():
                zipf.write(file_path, archive_path)
                logger.info(f"Added {archive_path} to package")

        logger.info(f"Package created: {zip_path}")
        logger.info(f"Dependencies: {', '.join(sorted(self.external_deps))}")

        return zip_path


def main():
    parser = argparse.ArgumentParser(
        description="Package Python modules with dependencies"
    )
    parser.add_argument(
        "module", help="Module name to package (e.g., mcp_hubspot_connector)"
    )
    parser.add_argument(
        "venv_path",
        help="Virtual environment path (e.g., /var/python3.11/silvaengine/env)",
    )
    parser.add_argument(
        "--output-dir", help="Output directory for ZIP file", default="."
    )
    parser.add_argument(
        "--additional-modules",
        help="Additional modules to include, separated by commas (e.g., module1,module2,module3)",
        default="",
    )

    args = parser.parse_args()

    packager = ModulePackager(args.venv_path)

    # Process additional modules if provided
    additional_modules = []
    if args.additional_modules:
        additional_modules = [
            module.strip()
            for module in args.additional_modules.split(",")
            if module.strip()
        ]
        logger.info(f"Additional modules to include: {additional_modules}")

    zip_path = packager.create_package(args.module, args.output_dir, additional_modules)

    if zip_path:
        print(f"Successfully created package: {zip_path}")
    else:
        print("Failed to create package")
        sys.exit(1)


if __name__ == "__main__":
    main()
