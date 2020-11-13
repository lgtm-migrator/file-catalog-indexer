"""Recursively get all filepaths in given directory and split into chunks.

These chunks are outputted files, which are used as input in
indexer_make_dag.py jobs.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime as dt
from typing import List, Union


def _full_path(path: str) -> str:
    if not path:
        return path

    full_path = os.path.abspath(path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(full_path)

    return full_path


def check_call_print(
    cmd: Union[List[str], str], cwd: str = ".", shell: bool = False
) -> None:
    """Wrap subprocess.check_call and print command."""
    if shell and isinstance(cmd, list):
        raise Exception("Do not set shell=True and pass a list--pass a string.")
    print(f"Execute: {cmd} @ {cwd}")
    subprocess.check_call(cmd, cwd=cwd, shell=shell)


def _full_traverse(
    exclude: List[str], paths_root: str, workers: int, output_root: str,
) -> str:
    """Get all file-paths in paths_root and sort the list."""
    file_orig = os.path.join(output_root, "paths.orig")
    file_sort = os.path.join(output_root, "paths.sort")
    file_log = os.path.join(output_root, "paths.log")

    exculdes_args = ""
    if exclude:
        exculdes_args = "--exclude " + " ".join(exclude)
    check_call_print(
        f"python directory_scanner.py {paths_root} --workers {workers} {exculdes_args} > {file_orig} 2> {file_log}",
        shell=True,
    )
    check_call_print(
        f"""sed -i '/^[[:space:]]*$/d' {file_orig}""", shell=True
    )  # remove blanks
    check_call_print(f"sort -T {output_root} {file_orig} > {file_sort}", shell=True)
    check_call_print(f"rm {file_orig}".split())  # Cleanup

    return file_sort


def _remove_already_collected_files(previous: str, file_sort: str) -> None:
    """Get lines(filepaths) unique to this scan versus the previous file."""
    if previous:
        check_call_print(
            f"comm -1 -3 {previous} {file_sort} > {file_sort}.unique", shell=True
        )
        check_call_print(f"mv {file_sort}.unique {file_sort}".split())


def _split(output_root: str, paths_per_file: int, file_sort: str) -> None:
    """Split the file into n files."""
    dir_split = os.path.join(output_root, "paths/")

    check_call_print(f"mkdir {dir_split}".split())
    # TODO - split by quota
    check_call_print(
        f"split -l{paths_per_file} {file_sort} paths_file_".split(), cwd=dir_split
    )


def _archive(staging_dir: str, name: str, file_sort: str) -> None:
    """Copy/Archive traverse into a file.

    Example:
    /data/user/eevans/data-exp-2020-03-10T15:11:42
    """
    time = dt.now().isoformat(timespec="seconds")
    file_archive = os.path.join(staging_dir, f"{name}-{time}")
    check_call_print(f"mv {file_sort} {file_archive}".split())
    print(f"Archive File: at {file_archive}")


def write_all_filepaths_to_files(  # pylint: disable=R0913
    staging_dir: str,
    paths_root: str,
    workers: int,
    previous: str,
    paths_per_file: int,
    exclude: List[str],
) -> None:
    """Write all filepaths (rooted from `paths_root`) to multiple files."""
    name = paths_root.strip("/").replace("/", "-")  # Ex: 'data-exp'
    if exclude:
        name += "-W-EXCLS"

    output_root = os.path.join(staging_dir, f"indexer-{name}/")

    if not os.path.exists(output_root):
        check_call_print(f"mkdir {output_root}".split())

        # output argv to a file
        with open(os.path.join(output_root, "argv.txt"), "w") as f:
            f.write(" ".join(sys.argv))

        file_sort = _full_traverse(exclude, paths_root, workers, output_root)
        _remove_already_collected_files(previous, file_sort)
        _split(output_root, paths_per_file, file_sort)
        _archive(staging_dir, name, file_sort)

    else:
        print(f"Writing Bypassed: {output_root} already exists. Use preexisting files.")


def main() -> None:
    """Get all filepaths rooted at directory and split-up/write to files."""
    parser = argparse.ArgumentParser(
        description="Run this script via all_paths_make_condor.py."
    )
    parser.add_argument(
        "paths_root",
        help="root directory to recursively scan for files.",
        type=_full_path,
    )
    parser.add_argument(
        "--staging-dir",
        dest="staging_dir",
        type=_full_path,
        required=True,
        help="the base directory to store files for jobs, eg: /data/user/eevans/",
    )
    parser.add_argument(
        "--previous-all-paths",
        dest="previous_all_paths",
        type=_full_path,
        help="prior file with file paths, eg: /data/user/eevans/data-exp-2020-03-10T15:11:42."
        " These files will be skipped.",
    )
    parser.add_argument(
        "--exclude",
        "-e",
        nargs="*",
        default=[],
        type=_full_path,
        help='directories/paths to exclude from the traverse -- keep it short, this is "all paths" after all.',
    )
    parser.add_argument(
        "--workers", type=int, help="max number of workers", required=True
    )
    parser.add_argument(
        "--paths-per-file",
        dest="paths_per_file",
        type=int,
        default=1000,
        help="number of paths per file/job",
    )
    args = parser.parse_args()

    for arg, val in vars(args).items():
        print(f"{arg}: {val}")

    write_all_filepaths_to_files(
        args.staging_dir,
        args.paths_root,
        args.workers,
        args.previous_all_paths,
        args.paths_per_file,
        args.exclude,
    )


if __name__ == "__main__":
    main()
