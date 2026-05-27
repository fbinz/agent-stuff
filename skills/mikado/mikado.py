#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pyyaml"]
# requires-python = ">=3.10"
# ///
"""CLI tool for maintaining a Mikado refactoring graph (mikado.yaml)."""

import argparse
import sys
from pathlib import Path

import yaml


DEFAULT_FILE = "mikado.yaml"


def load(path: Path) -> dict:
    if not path.exists():
        print(f"error: {path} not found", file=sys.stderr)
        sys.exit(2)
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "nodes" not in data or "goal" not in data:
        print(f"error: {path} is not a valid mikado graph", file=sys.stderr)
        sys.exit(1)
    return data


def save(path: Path, data: dict):
    validate_graph(data)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def validate_graph(data: dict, quiet: bool = True) -> bool:
    nodes = data.get("nodes", {})
    ok = True

    for nid, node in nodes.items():
        for dep in node.get("deps", []):
            if dep not in nodes:
                print(f"error: node '{nid}' has dangling dep '{dep}'", file=sys.stderr)
                ok = False
        if node.get("status") not in ("pending", "in-progress", "done"):
            print(f"error: node '{nid}' has invalid status '{node.get('status')}'", file=sys.stderr)
            ok = False

    if has_cycle(nodes):
        print("error: graph contains a cycle", file=sys.stderr)
        ok = False

    if ok and not quiet:
        print("graph is valid")
    return ok


def has_cycle(nodes: dict) -> bool:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}

    def dfs(nid):
        color[nid] = GRAY
        for dep in nodes[nid].get("deps", []):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                return True
            if color[dep] == WHITE and dfs(dep):
                return True
        color[nid] = BLACK
        return False

    return any(color[nid] == WHITE and dfs(nid) for nid in nodes)


def get_leaves(nodes: dict) -> list[str]:
    leaves = []
    for nid, node in nodes.items():
        if node.get("status") == "done":
            continue
        deps = node.get("deps", [])
        if all(nodes.get(d, {}).get("status") == "done" for d in deps):
            leaves.append(nid)
    return leaves


def get_in_progress(nodes: dict) -> str | None:
    for nid, node in nodes.items():
        if node.get("status") == "in-progress":
            return nid
    return None


def print_node(nid: str, node: dict):
    print(f"  {nid}:")
    print(f"    desc: {node['desc']}")
    print(f"    status: {node['status']}")
    print(f"    deps: {node.get('deps', [])}")
    detail = node.get("detail")
    if detail:
        if detail.get("files"):
            print(f"    files: {detail['files']}")
        if detail.get("change"):
            print(f"    change: {detail['change']}")
        if detail.get("verify"):
            print(f"    verify: {detail['verify']}")
        if detail.get("context"):
            print(f"    context: {detail['context'].rstrip()}")


# --- commands ---


def cmd_init(args):
    path = Path(args.file)
    if path.exists() and not args.force:
        print(f"error: {path} already exists (use --force to overwrite)", file=sys.stderr)
        sys.exit(1)
    data = {
        "goal": args.goal,
        "nodes": {
            "goal": {
                "desc": args.goal,
                "deps": [],
                "status": "pending",
            }
        },
    }
    save(path, data)
    print(f"created {path}")


def cmd_add(args):
    path = Path(args.file)
    data = load(path)
    nodes = data["nodes"]
    if args.id in nodes:
        print(f"error: node '{args.id}' already exists", file=sys.stderr)
        sys.exit(1)
    deps = [d.strip() for d in args.deps.split(",") if d.strip()] if args.deps else []
    for dep in deps:
        if dep not in nodes:
            print(f"error: dep '{dep}' does not exist", file=sys.stderr)
            sys.exit(1)
    nodes[args.id] = {"desc": args.desc, "deps": deps, "status": "pending"}
    if args.parent:
        if args.parent not in nodes:
            print(f"error: parent '{args.parent}' does not exist", file=sys.stderr)
            sys.exit(1)
        parent = nodes[args.parent]
        if args.id not in parent.get("deps", []):
            parent.setdefault("deps", []).append(args.id)
    save(path, data)
    print(f"added '{args.id}'")


def cmd_leaves(args):
    data = load(Path(args.file))
    leaves = get_leaves(data["nodes"])
    if not leaves:
        print("no workable leaves")
    else:
        for nid in leaves:
            print_node(nid, data["nodes"][nid])


def cmd_next(args):
    path = Path(args.file)
    data = load(path)
    nodes = data["nodes"]
    current = get_in_progress(nodes)
    if current:
        print(f"already in-progress: '{current}'", file=sys.stderr)
        sys.exit(1)
    leaves = get_leaves(nodes)
    if not leaves:
        print("no workable leaves", file=sys.stderr)
        sys.exit(1)
    nid = leaves[0]
    nodes[nid]["status"] = "in-progress"
    save(path, data)
    print(f"started '{nid}':")
    print_node(nid, nodes[nid])


def cmd_done(args):
    path = Path(args.file)
    data = load(path)
    nodes = data["nodes"]
    nid = args.id or get_in_progress(nodes)
    if not nid:
        print("error: no node specified and none in-progress", file=sys.stderr)
        sys.exit(1)
    if nid not in nodes:
        print(f"error: node '{nid}' does not exist", file=sys.stderr)
        sys.exit(1)
    if nodes[nid]["status"] == "done":
        print(f"error: node '{nid}' is already done", file=sys.stderr)
        sys.exit(1)
    nodes[nid]["status"] = "done"
    save(path, data)
    print(f"completed '{nid}'")
    leaves = get_leaves(nodes)
    if leaves:
        print(f"next leaves: {', '.join(leaves)}")
    elif all(n["status"] == "done" for n in nodes.values()):
        print("all nodes done — goal achieved!")


def cmd_revert(args):
    path = Path(args.file)
    data = load(path)
    nodes = data["nodes"]
    nid = args.id or get_in_progress(nodes)
    if not nid:
        print("error: no node specified and none in-progress", file=sys.stderr)
        sys.exit(1)
    if nid not in nodes:
        print(f"error: node '{nid}' does not exist", file=sys.stderr)
        sys.exit(1)
    if nodes[nid]["status"] != "in-progress":
        print(f"error: node '{nid}' is not in-progress (status: {nodes[nid]['status']})", file=sys.stderr)
        sys.exit(1)
    nodes[nid]["status"] = "pending"
    save(path, data)
    print(f"reverted '{nid}' to pending")


def cmd_detail(args):
    path = Path(args.file)
    data = load(path)
    nodes = data["nodes"]
    if args.id not in nodes:
        print(f"error: node '{args.id}' does not exist", file=sys.stderr)
        sys.exit(1)
    detail = nodes[args.id].setdefault("detail", {})
    if args.files:
        detail["files"] = [f.strip() for f in args.files.split(",")]
    if args.change:
        detail["change"] = args.change
    if args.verify:
        detail["verify"] = args.verify
    if args.context:
        detail["context"] = args.context
    save(path, data)
    print(f"updated detail for '{args.id}'")


def cmd_show(args):
    data = load(Path(args.file))
    nodes = data["nodes"]
    if args.id not in nodes:
        print(f"error: node '{args.id}' does not exist", file=sys.stderr)
        sys.exit(1)
    print_node(args.id, nodes[args.id])


def cmd_status(args):
    data = load(Path(args.file))
    nodes = data["nodes"]
    total = len(nodes)
    done = sum(1 for n in nodes.values() if n["status"] == "done")
    in_prog = get_in_progress(nodes)
    pending = total - done - (1 if in_prog else 0)
    leaves = get_leaves(nodes)
    print(f"goal: {data['goal']}")
    print(f"nodes: {total} total, {done} done, {1 if in_prog else 0} in-progress, {pending} pending")
    if in_prog:
        print(f"working on: {in_prog}")
    if leaves:
        print(f"leaves: {', '.join(leaves)}")
    else:
        if done == total:
            print("all nodes done — goal achieved!")
        else:
            print("no workable leaves (blocked)")


def cmd_validate(args):
    data = load(Path(args.file))
    if validate_graph(data, quiet=False):
        sys.exit(0)
    else:
        sys.exit(1)


def cmd_graph(args):
    data = load(Path(args.file))
    nodes = data["nodes"]
    dependents = {nid: [] for nid in nodes}
    for nid, node in nodes.items():
        for dep in node.get("deps", []):
            if dep in dependents:
                dependents[dep].append(nid)

    roots = [nid for nid, node in nodes.items() if not any(nid in n.get("deps", []) for n in nodes.values())]
    if not roots:
        roots = ["goal"]

    printed = set()

    def print_tree(nid, prefix="", is_last=True):
        if nid in printed:
            connector = "└── " if is_last else "├── "
            print(f"{prefix}{connector}{nid} [{nodes[nid]['status']}] (see above)")
            return
        printed.add(nid)
        connector = "└── " if is_last else "├── "
        status = nodes[nid]["status"]
        marker = {"done": "✓", "in-progress": "→", "pending": "○"}[status]
        print(f"{prefix}{connector}{marker} {nid}: {nodes[nid]['desc']}")
        children = [d for d in nodes[nid].get("deps", []) if d in nodes]
        for i, child in enumerate(children):
            extension = "    " if is_last else "│   "
            print_tree(child, prefix + extension, i == len(children) - 1)

    for i, root in enumerate(roots):
        if i > 0:
            print()
        status = nodes[root]["status"]
        marker = {"done": "✓", "in-progress": "→", "pending": "○"}[status]
        print(f"{marker} {root}: {nodes[root]['desc']}")
        children = [d for d in nodes[root].get("deps", []) if d in nodes]
        printed.add(root)
        for j, child in enumerate(children):
            print_tree(child, "", j == len(children) - 1)


def main():
    parser = argparse.ArgumentParser(prog="mikado", description="Maintain a Mikado refactoring graph.")
    parser.add_argument("-f", "--file", default=DEFAULT_FILE, help=f"path to graph file (default: {DEFAULT_FILE})")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create a new mikado graph")
    p.add_argument("goal", help="the refactoring goal")
    p.add_argument("--force", action="store_true", help="overwrite existing file")

    p = sub.add_parser("add", help="add a node")
    p.add_argument("id", help="node id (kebab-case)")
    p.add_argument("desc", help="what this node accomplishes")
    p.add_argument("--deps", help="comma-separated dep IDs")
    p.add_argument("--parent", help="add this node as a dep of an existing node")

    p = sub.add_parser("leaves", help="list workable leaf nodes")

    p = sub.add_parser("next", help="pick a leaf and start working on it")

    p = sub.add_parser("done", help="mark a node as done")
    p.add_argument("id", nargs="?", help="node id (default: current in-progress)")

    p = sub.add_parser("revert", help="reset in-progress node to pending")
    p.add_argument("id", nargs="?", help="node id (default: current in-progress)")

    p = sub.add_parser("detail", help="set implementation detail on a node")
    p.add_argument("id", help="node id")
    p.add_argument("--files", help="comma-separated file paths")
    p.add_argument("--change", help="what to do")
    p.add_argument("--verify", help="command to confirm green")
    p.add_argument("--context", help="free-form notes")

    p = sub.add_parser("show", help="show a node")
    p.add_argument("id", help="node id")

    sub.add_parser("status", help="print graph summary")
    sub.add_parser("validate", help="check graph integrity")
    sub.add_parser("graph", help="print the DAG as a tree")

    args = parser.parse_args()
    {
        "init": cmd_init,
        "add": cmd_add,
        "leaves": cmd_leaves,
        "next": cmd_next,
        "done": cmd_done,
        "revert": cmd_revert,
        "detail": cmd_detail,
        "show": cmd_show,
        "status": cmd_status,
        "validate": cmd_validate,
        "graph": cmd_graph,
    }[args.command](args)


if __name__ == "__main__":
    main()
