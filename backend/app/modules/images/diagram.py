"""Turns a small diagram spec (nodes + edges) into a clean, draw.io-style SVG.

The language model only has to describe *what* is in the diagram. Layout, shapes,
colours and connector routing are done here, so the output is always tidy. The SVG
also carries the matching draw.io (mxfile) XML in its `content` attribute, which is
how diagrams.net saves editable SVG files: open the SVG there and every shape and
connector can be edited.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field

KINDS = ("process", "start", "end", "decision", "database", "io", "external")

# draw.io default palette: kind -> (fill, stroke)
PALETTE = {
    "process": ("#dae8fc", "#6c8ebf"),
    "start": ("#d5e8d4", "#82b366"),
    "end": ("#f8cecc", "#b85450"),
    "decision": ("#fff2cc", "#d6b656"),
    "database": ("#e1d5e7", "#9673a6"),
    "io": ("#ffe6cc", "#d79b00"),
    "external": ("#f5f5f5", "#666666"),
}

# draw.io style strings, so the SVG opens as editable shapes in diagrams.net
MX_STYLE = {
    "process": "rounded=1;whiteSpace=wrap;html=1;",
    "start": "rounded=1;whiteSpace=wrap;html=1;arcSize=50;",
    "end": "rounded=1;whiteSpace=wrap;html=1;arcSize=50;",
    "decision": "rhombus;whiteSpace=wrap;html=1;",
    "database": "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;",
    "io": "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fixedSize=1;",
    "external": "ellipse;whiteSpace=wrap;html=1;fontColor=#333333;",
}

FONT = "Helvetica, Arial, sans-serif"
FONT_SIZE = 13
CHAR_W = 7.4
LINE_H = 17
LAYER_GAP = 84
NODE_GAP = 56
DUMMY_GAP = 30
MARGIN = 28
MAX_NODES = 26


@dataclass
class Node:
    id: str
    label: str
    kind: str = "process"
    lines: list[str] = field(default_factory=list)
    w: float = 0
    h: float = 0
    # layout
    layer: int = 0
    a: float = 0  # centre along the layer
    b: float = 0  # centre across layers
    dummy: bool = False


@dataclass
class Edge:
    src: str
    dst: str
    label: str = ""


# ------------------------------------------------------------------ parsing
def parse_spec(raw: str) -> dict:
    """Pulls the JSON object out of a model reply and tidies it into a safe spec."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("The model did not return a diagram.")
    data = json.loads(text[start : end + 1])

    nodes: dict[str, Node] = {}
    for item in data.get("nodes") or []:
        if not isinstance(item, dict):
            continue
        nid = str(item.get("id", "")).strip()
        label = str(item.get("label", "") or nid).strip()
        if not nid or nid in nodes:
            continue
        kind = str(item.get("kind", "process")).strip().lower()
        nodes[nid] = Node(nid, label[:60], kind if kind in KINDS else "process")

    edges: list[Edge] = []
    seen: set[tuple[str, str]] = set()
    for item in data.get("edges") or []:
        if not isinstance(item, dict):
            continue
        src = str(item.get("from", item.get("source", ""))).strip()
        dst = str(item.get("to", item.get("target", ""))).strip()
        if not src or not dst or src == dst or (src, dst) in seen:
            continue
        by_label = {n.label.lower(): n.id for n in nodes.values()}
        src, dst = by_label.get(src.lower(), src), by_label.get(dst.lower(), dst)
        if src not in nodes or dst not in nodes or src == dst or (src, dst) in seen:
            continue
        seen.add((src, dst))
        edges.append(Edge(src, dst, str(item.get("label", "") or "").strip()[:24]))

    linked = {e.src for e in edges} | {e.dst for e in edges}
    nodes = {k: v for k, v in nodes.items() if k in linked}
    if len(nodes) < 2 or not edges:
        raise ValueError("The model returned too little to draw a diagram.")
    if len(nodes) > MAX_NODES:
        keep = list(nodes)[:MAX_NODES]
        nodes = {k: nodes[k] for k in keep}
        edges = [e for e in edges if e.src in nodes and e.dst in nodes]

    direction = str(data.get("direction", "TB")).upper()
    return {
        "title": str(data.get("title", "") or "").strip()[:80],
        "direction": "LR" if direction == "LR" else "TB",
        "nodes": list(nodes.values()),
        "edges": edges,
    }


# ------------------------------------------------------------------ sizing
def wrap_label(label: str, width: int) -> list[str]:
    words, lines, cur = label.split(), [], ""
    for word in words:
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def size_node(n: Node) -> None:
    width = 15 if n.kind == "decision" else 22
    n.lines = wrap_label(n.label, width)
    tw = max(len(line) for line in n.lines) * CHAR_W
    th = len(n.lines) * LINE_H
    if n.kind == "decision":
        n.w, n.h = max(150, tw * 1.55 + 24), max(90, th * 2.0 + 24)
    elif n.kind == "database":
        n.w, n.h = max(110, tw + 36), max(84, th + 54)
    elif n.kind in ("start", "end"):
        n.w, n.h = max(116, tw + 48), max(48, th + 24)
    elif n.kind == "io":
        n.w, n.h = max(140, tw + 64), max(56, th + 26)
    elif n.kind == "external":
        n.w, n.h = max(120, tw * 1.25 + 28), max(64, th + 38)
    else:
        n.w, n.h = max(120, tw + 36), max(56, th + 28)


# ------------------------------------------------------------------ layout
def _break_cycles(ids: list[str], edges: list[Edge]) -> list[tuple[str, str, Edge, bool]]:
    """Returns (from, to, edge, reversed) with no cycles, using DFS back-edge reversal."""
    adj: dict[str, list[str]] = {i: [] for i in ids}
    for e in edges:
        adj[e.src].append(e.dst)
    state: dict[str, int] = {}
    back: set[tuple[str, str]] = set()

    def visit(u: str) -> None:
        state[u] = 1
        for v in adj[u]:
            if state.get(v) == 1:
                back.add((u, v))
            elif state.get(v) is None:
                visit(v)
        state[u] = 2

    indeg = {i: 0 for i in ids}
    for e in edges:
        indeg[e.dst] += 1
    for i in [i for i in ids if indeg[i] == 0] + ids:
        if state.get(i) is None:
            visit(i)
    out = []
    for e in edges:
        if (e.src, e.dst) in back:
            out.append((e.dst, e.src, e, True))
        else:
            out.append((e.src, e.dst, e, False))
    return out


def _pav(d: list[float], o: list[float]) -> list[float]:
    """Isotonic regression: closest values to d - o that never decrease (keeps nodes apart)."""
    blocks: list[list[float]] = []  # [sum, count]
    for v in (di - oi for di, oi in zip(d, o)):
        blocks.append([v, 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s, c = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += c
    y: list[float] = []
    for s, c in blocks:
        y += [s / c] * int(c)
    return [yi + oi for yi, oi in zip(y, o)]


def layout(spec: dict) -> dict:
    nodes: dict[str, Node] = {n.id: n for n in spec["nodes"]}
    edges: list[Edge] = spec["edges"]
    lr = spec["direction"] == "LR"
    for n in nodes.values():
        size_node(n)

    ordered = _break_cycles(list(nodes), edges)

    # layers (longest path)
    preds: dict[str, list[str]] = {i: [] for i in nodes}
    for u, v, _, _ in ordered:
        preds[v].append(u)
    layer: dict[str, int] = {}

    def depth(i: str) -> int:
        if i not in layer:
            layer[i] = 0  # guards against any leftover cycle
            layer[i] = max((depth(p) + 1 for p in preds[i]), default=0)
        return layer[i]

    for i in nodes:
        depth(i)
    for i, n in nodes.items():
        n.layer = layer[i]

    # dummy nodes for edges that span several layers
    chains: list[tuple[Edge, bool, list[str]]] = []
    count = 0
    for u, v, e, rev in ordered:
        chain = [u]
        for k in range(nodes[u].layer + 1, nodes[v].layer):
            did = f"_d{count}"
            count += 1
            d = Node(did, "", "dummy", dummy=True, layer=k)
            d.w = d.h = 0
            nodes[did] = d
            chain.append(did)
        chain.append(v)
        chains.append((e, rev, chain))

    def along(n: Node) -> float:  # size along the layer
        return 6 if n.dummy else (n.h if lr else n.w)

    def across(n: Node) -> float:  # size across layers
        return 0 if n.dummy else (n.w if lr else n.h)

    n_layers = max(n.layer for n in nodes.values()) + 1
    rows: list[list[str]] = [[] for _ in range(n_layers)]
    for i in nodes:
        rows[nodes[i].layer].append(i)

    up: dict[str, list[str]] = {i: [] for i in nodes}
    down: dict[str, list[str]] = {i: [] for i in nodes}
    for _, _, chain in chains:
        for p, q in zip(chain, chain[1:]):
            down[p].append(q)
            up[q].append(p)

    # order nodes inside layers (barycentre sweeps)
    pos = {i: k for row in rows for k, i in enumerate(row)}
    for sweep in range(12):
        seq = range(1, n_layers) if sweep % 2 == 0 else range(n_layers - 2, -1, -1)
        for L in seq:
            nbr = up if sweep % 2 == 0 else down
            def key(i: str) -> float:
                ns = nbr[i]
                return sum(pos[x] for x in ns) / len(ns) if ns else pos[i]
            rows[L].sort(key=key)
            for k, i in enumerate(rows[L]):
                pos[i] = k

    # coordinates along the layer: start packed, then pull towards neighbours
    gaps: list[list[float]] = []
    offs: list[list[float]] = []
    for row in rows:
        g, o, cur = [], [], 0.0
        for k, i in enumerate(row):
            if k:
                prev = nodes[row[k - 1]]
                cur += (along(prev) + along(nodes[i])) / 2 + (DUMMY_GAP if prev.dummy or nodes[i].dummy else NODE_GAP)
            o.append(cur)
            g.append(0.0)
        offs.append(o)
        gaps.append(g)
        for k, i in enumerate(row):
            nodes[i].a = o[k]
    for it in range(16):
        seq = range(n_layers) if it % 2 == 0 else range(n_layers - 1, -1, -1)
        for L in seq:
            row = rows[L]
            want = []
            for i in row:
                ns = (up[i] + down[i]) if it >= 8 else (up[i] if it % 2 == 0 else down[i])
                want.append(sum(nodes[x].a for x in ns) / len(ns) if ns else nodes[i].a)
            new = _pav(want, offs[L])
            for k, i in enumerate(row):
                nodes[i].a = new[k]

    lo = min(nodes[i].a - along(nodes[i]) / 2 for i in nodes if not nodes[i].dummy)
    for n in nodes.values():
        n.a += MARGIN - lo

    # coordinates across layers
    gap_mid: list[float] = []
    cursor = float(MARGIN)
    layer_top: list[float] = []
    layer_bot: list[float] = []
    for row in rows:
        size = max((across(nodes[i]) for i in row), default=0)
        layer_top.append(cursor)
        for i in row:
            nodes[i].b = cursor + size / 2
        cursor += size
        layer_bot.append(cursor)
        cursor += LAYER_GAP
    for L in range(n_layers - 1):
        gap_mid.append((layer_bot[L] + layer_top[L + 1]) / 2)

    # real x/y for every node
    for n in nodes.values():
        n.x_c, n.y_c = (n.b, n.a) if lr else (n.a, n.b)  # type: ignore[attr-defined]

    # edge routing (orthogonal, one bend row per gap, offset per source)
    srcs_by_gap: dict[int, list[str]] = {}
    for _, rev, chain in chains:
        for p in chain[:-1]:
            L = nodes[p].layer
            srcs_by_gap.setdefault(L, [])
            if p not in srcs_by_gap[L]:
                srcs_by_gap[L].append(p)
    for L in srcs_by_gap:
        srcs_by_gap[L].sort(key=lambda i: nodes[i].a)

    # decision nodes send their first/last outgoing edge out of the left/right corner
    side: dict[int, int] = {}
    outs: dict[str, list[int]] = {}
    for k, (e, rev, chain) in enumerate(chains):
        if not rev:
            outs.setdefault(chain[0], []).append(k)
    for src, ks in outs.items():
        n = nodes[src]
        if n.kind != "decision" or len(ks) < 2:
            continue
        ks.sort(key=lambda k: nodes[chains[k][2][1]].a)
        half = along(n) / 2
        if nodes[chains[ks[0]][2][1]].a < n.a - half - 10:
            side[ks[0]] = -1
        if nodes[chains[ks[-1]][2][1]].a > n.a + half + 10:
            side[ks[-1]] = 1

    routes = []
    for k, (e, rev, chain) in enumerate(chains):
        pts: list[tuple[float, float]] = []  # in (a, b) space
        first, last = nodes[chain[0]], nodes[chain[-1]]
        off = min(26.0, along(first) / 4, along(last) / 4) if rev else 0.0
        fa, la = first.a + off, last.a + off
        steps = list(zip(chain, chain[1:]))
        if len(chain) == 2 and abs(first.a - last.a) < 14 and k not in side and not rev:
            pts = [(first.a, first.b + across(first) / 2), (first.a, last.b - across(last) / 2)]
            steps = []
        elif k in side:
            sd = side[k]
            pts.append((first.a + sd * along(first) / 2, first.b))
            pts.append((nodes[chain[1]].a, first.b))
            steps = steps[1:]
        else:
            pts.append((fa, first.b + across(first) / 2))
        for p, q in steps:
            L = nodes[p].layer
            group = srcs_by_gap[L]
            step = min(10.0, (LAYER_GAP / 2 - 12) / max(1, len(group)))
            ym = gap_mid[L] + (group.index(p) - (len(group) - 1) / 2) * step
            pa = fa if p == chain[0] else nodes[p].a
            qa = la if q == chain[-1] else nodes[q].a
            pts.append((pa, ym))
            pts.append((qa, ym))
        if steps or k in side:
            pts.append((la, last.b - across(last) / 2))
        # drop repeated and straight-through points
        clean: list[tuple[float, float]] = []
        for pt in pts:
            if clean and abs(clean[-1][0] - pt[0]) < 0.5 and abs(clean[-1][1] - pt[1]) < 0.5:
                continue
            clean.append(pt)
        k = 1
        while k < len(clean) - 1:
            (x0, y0), (x1, y1), (x2, y2) = clean[k - 1], clean[k], clean[k + 1]
            if (abs(x0 - x1) < 0.5 and abs(x1 - x2) < 0.5) or (abs(y0 - y1) < 0.5 and abs(y1 - y2) < 0.5):
                clean.pop(k)
            else:
                k += 1
        if lr:
            clean = [(b, a) for a, b in clean]
        if rev:
            clean.reverse()
        routes.append((e, clean))

    xs = [n.x_c - n.w / 2 for n in nodes.values() if not n.dummy]  # type: ignore[attr-defined]
    ys = [n.y_c - n.h / 2 for n in nodes.values() if not n.dummy]  # type: ignore[attr-defined]
    xe = [n.x_c + n.w / 2 for n in nodes.values() if not n.dummy]  # type: ignore[attr-defined]
    ye = [n.y_c + n.h / 2 for n in nodes.values() if not n.dummy]  # type: ignore[attr-defined]
    for _, pts in routes:
        for x, y in pts:
            xs.append(x), xe.append(x), ys.append(y), ye.append(y)
    return {
        "nodes": [n for n in nodes.values() if not n.dummy],
        "routes": routes,
        "width": max(xe) + MARGIN,
        "height": max(ye) + MARGIN,
        "min_x": min(xs),
        "min_y": min(ys),
    }


# ------------------------------------------------------------------ rendering
def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _shape(n: Node, ox: float, oy: float) -> str:
    fill, stroke = PALETTE[n.kind]
    x, y = n.x_c - n.w / 2 - ox, n.y_c - n.h / 2 - oy  # type: ignore[attr-defined]
    w, h = n.w, n.h
    attrs = f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"'
    if n.kind == "decision":
        pts = f"{x + w / 2},{y} {x + w},{y + h / 2} {x + w / 2},{y + h} {x},{y + h / 2}"
        body = f'<polygon points="{pts}" {attrs} stroke-linejoin="round"/>'
    elif n.kind in ("start", "end"):
        body = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" {attrs}/>'
    elif n.kind == "io":
        s = 18
        pts = f"{x + s},{y} {x + w},{y} {x + w - s},{y + h} {x},{y + h}"
        body = f'<polygon points="{pts}" {attrs} stroke-linejoin="round"/>'
    elif n.kind == "external":
        body = f'<ellipse cx="{x + w / 2}" cy="{y + h / 2}" rx="{w / 2}" ry="{h / 2}" {attrs}/>'
    elif n.kind == "database":
        ry = min(15, h * 0.18)
        rx = w / 2
        d = (
            f"M{x},{y + ry} A{rx},{ry} 0 0 1 {x + w},{y + ry} V{y + h - ry} "
            f"A{rx},{ry} 0 0 1 {x},{y + h - ry} Z"
        )
        top = f"M{x},{y + ry} A{rx},{ry} 0 0 0 {x + w},{y + ry}"
        body = f'<path d="{d}" {attrs}/><path d="{top}" fill="none" stroke="{stroke}" stroke-width="1.6"/>'
    else:
        body = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" {attrs}/>'
    ty = y + h / 2 - (len(n.lines) - 1) * LINE_H / 2 + 5
    if n.kind == "database":
        ty += 7
    tcolor = "#333333" if n.kind == "external" else "#1a1a1a"
    tspans = "".join(
        f'<tspan x="{x + w / 2}" y="{ty + k * LINE_H}">{_esc(line)}</tspan>' for k, line in enumerate(n.lines)
    )
    return (
        f'<g>{body}<text font-family="{FONT}" font-size="{FONT_SIZE}" fill="{tcolor}" '
        f'text-anchor="middle">{tspans}</text></g>'
    )


def _path(pts: list[tuple[float, float]], r: float = 9) -> str:
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for k in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[k - 1], pts[k], pts[k + 1]
        l1 = abs(x1 - x0) + abs(y1 - y0)
        l2 = abs(x2 - x1) + abs(y2 - y1)
        rr = min(r, l1 / 2, l2 / 2)
        ax = x1 - (x1 - x0) / l1 * rr if l1 else x1
        ay = y1 - (y1 - y0) / l1 * rr if l1 else y1
        bx = x1 + (x2 - x1) / l2 * rr if l2 else x1
        by = y1 + (y2 - y1) / l2 * rr if l2 else y1
        d += f" L{ax:.1f},{ay:.1f} Q{x1:.1f},{y1:.1f} {bx:.1f},{by:.1f}"
    d += f" L{pts[-1][0]:.1f},{pts[-1][1]:.1f}"
    return d


def _label_spot(pts: list[tuple[float, float]]) -> tuple[float, float]:
    segs = list(zip(pts, pts[1:]))
    x0, y0, x1, y1 = (*segs[0][0], *segs[0][1])
    if abs(x1 - x0) + abs(y1 - y0) >= 34:
        return (x0 + x1) / 2, (y0 + y1) / 2
    best = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
    return (best[0][0] + best[1][0]) / 2, (best[0][1] + best[1][1]) / 2


def mxfile(title: str, lay: dict) -> str:
    ox, oy = lay["min_x"] - MARGIN, lay["min_y"] - MARGIN
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    ids: dict[str, str] = {}
    for k, n in enumerate(lay["nodes"]):
        cid = f"n{k + 2}"
        ids[n.id] = cid
        fill, stroke = PALETTE[n.kind]
        style = f"{MX_STYLE[n.kind]}fillColor={fill};strokeColor={stroke};"
        cells.append(
            f'<mxCell id="{cid}" value="{_esc(n.label)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{n.x_c - n.w / 2 - ox:.0f}" y="{n.y_c - n.h / 2 - oy:.0f}" '
            f'width="{n.w:.0f}" height="{n.h:.0f}" as="geometry"/></mxCell>'  # type: ignore[attr-defined]
        )
    for k, (e, pts) in enumerate(lay["routes"]):
        mid = "".join(f'<mxPoint x="{x - ox:.0f}" y="{y - oy:.0f}"/>' for x, y in pts[1:-1])
        arr = f'<Array as="points">{mid}</Array>' if mid else ""
        cells.append(
            f'<mxCell id="e{k}" value="{_esc(e.label)}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;'
            f'orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;endFill=1;" edge="1" parent="1" '
            f'source="{ids[e.src]}" target="{ids[e.dst]}"><mxGeometry relative="1" as="geometry">{arr}'
            f"</mxGeometry></mxCell>"
        )
    return (
        '<mxfile host="app.diagrams.net" agent="CodeHaven"><diagram id="codehaven" name="Page-1">'
        '<mxGraphModel dx="1000" dy="700" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
        'arrows="1" fold="1" page="0" pageScale="1" math="0" shadow="0"><root>'
        + "".join(cells)
        + "</root></mxGraphModel></diagram></mxfile>"
    )


def render(spec: dict) -> tuple[str, str]:
    """Returns (svg, mxfile_xml)."""
    lay = layout(spec)
    ox, oy = lay["min_x"] - MARGIN, lay["min_y"] - MARGIN
    width, height = lay["width"] - ox, lay["height"] - oy
    xml = mxfile(spec["title"], lay)

    parts = [
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="10" markerHeight="10" '
        'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#333333"/></marker></defs>',
        f'<rect width="{width:.0f}" height="{height:.0f}" fill="#ffffff"/>',
    ]
    for e, pts in lay["routes"]:
        shifted = [(x - ox, y - oy) for x, y in pts]
        parts.append(
            f'<path d="{_path(shifted)}" fill="none" stroke="#333333" stroke-width="1.6" '
            f'stroke-linejoin="round" marker-end="url(#arrow)"/>'
        )
    for n in lay["nodes"]:
        parts.append(_shape(n, ox, oy))
    for e, pts in lay["routes"]:
        if not e.label:
            continue
        lx, ly = _label_spot([(x - ox, y - oy) for x, y in pts])
        tw = len(e.label) * 7 + 12
        parts.append(
            f'<rect x="{lx - tw / 2:.1f}" y="{ly - 10:.1f}" width="{tw:.1f}" height="20" rx="4" fill="#ffffff"/>'
            f'<text x="{lx:.1f}" y="{ly + 4.5:.1f}" font-family="{FONT}" font-size="12" fill="#333333" '
            f'text-anchor="middle">{_esc(e.label)}</text>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{width:.0f}px" height="{height:.0f}px" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" content="{_esc(xml)}">'
        f"<title>{_esc(spec['title'] or 'Diagram')}</title>" + "".join(parts) + "</svg>"
    )
    return svg, xml
