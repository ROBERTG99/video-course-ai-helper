from __future__ import annotations

import re
from collections.abc import Callable

WIKI = re.compile(r"\[\[([^\]|#]+)")


def outline(md: str) -> list[tuple[int, str]]:
    """Nested '- ' list before the generated markers -> [(depth, label)]. Two spaces per level."""
    md = md.split("<!-- generated:start -->")[0]
    out: list[tuple[int, str]] = []
    for line in md.splitlines():
        m = re.match(r"^(\s*)- (.+)$", line)
        if m:
            out.append((len(m.group(1)) // 2, m.group(2).strip()))
    return out


def to_canvas(title: str, items: list[tuple[int, str]], resolve: Callable[[str], str | None]) -> dict:
    """Obsidian .canvas JSON (nodes+edges). Wikilinks that `resolve` maps to a vault path become file nodes."""
    nodes = [{"id": "root", "type": "text", "text": f"# {title}", "x": 0, "y": 45 * max(len(items) - 1, 0), "width": 320, "height": 80}]
    edges: list[dict] = []
    stack: list[str] = []
    for i, (depth, label) in enumerate(items):
        link = WIKI.search(label)
        path = resolve(link.group(1).strip()) if link else None
        node: dict = {"id": f"n{i}", "x": 400 * (depth + 1), "y": 90 * i, "width": 300, "height": 70}
        node.update({"type": "file", "file": path} if path else {"type": "text", "text": label})
        stack = stack[:depth]
        parent = stack[-1] if stack else "root"
        edges.append({"id": f"e{i}", "fromNode": parent, "toNode": node["id"], "fromSide": "right", "toSide": "left"})
        nodes.append(node)
        stack.append(node["id"])
    return {"nodes": nodes, "edges": edges}


def to_canvas_units(title: str, course: str, units: list, h2s: dict[str, list[str]]) -> dict:
    """Course -> units -> unit H2 sections. `units`: objects with .slug; `h2s`: unit slug -> its ## headings."""
    nodes: list[dict] = []
    edges: list[dict] = []
    i = 0
    for u in units:
        uid = f"u{i}"
        doc = f"{course}/unidades/{u.slug}.md"
        nodes.append({"id": uid, "type": "file", "file": doc, "x": 400, "y": 90 * i, "width": 300, "height": 70})
        edges.append({"id": f"e-{uid}", "fromNode": "root", "toNode": uid, "fromSide": "right", "toSide": "left"})
        i += 1
        for j, h in enumerate(h2s.get(u.slug, [])):
            hid = f"{uid}h{j}"
            nodes.append({"id": hid, "type": "file", "file": doc, "subpath": f"#{h}", "x": 800, "y": 90 * i,
                          "width": 300, "height": 70})
            edges.append({"id": f"e-{hid}", "fromNode": uid, "toNode": hid, "fromSide": "right", "toSide": "left"})
            i += 1
    root = {"id": "root", "type": "text", "text": f"# {title}", "x": 0, "y": 45 * max(i - 1, 0), "width": 320, "height": 80}
    return {"nodes": [root, *nodes], "edges": edges}
