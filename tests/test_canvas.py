import json

from pipeline import canvas

MOC = "# X\n\n## Mapa\n- Fundamentos\n  - [[capas]]\n  - [[mvc]]\n- Calidad\n  - [[acoplamiento]]\n\n<!-- generated:start -->\n- [[ignorado]]\n<!-- generated:end -->\n"


def test_outline_ignores_generated():
    assert canvas.outline(MOC) == [(0, "Fundamentos"), (1, "[[capas]]"), (1, "[[mvc]]"), (0, "Calidad"), (1, "[[acoplamiento]]")]


def test_to_canvas_tree():
    resolve = lambda name: f"arqui/temas/{name}.md" if name != "mvc" else None
    c = canvas.to_canvas("Arq", canvas.outline(MOC), resolve)
    assert c["nodes"][0]["id"] == "root" and len(c["nodes"]) == 6 and len(c["edges"]) == 5
    capas = next(n for n in c["nodes"] if n.get("file") == "arqui/temas/capas.md")
    mvc = next(n for n in c["nodes"] if n.get("text") == "[[mvc]]")
    assert capas["type"] == "file" and mvc["type"] == "text"
    e = next(e for e in c["edges"] if e["toNode"] == capas["id"])
    assert e["fromNode"] == next(n for n in c["nodes"] if n.get("text") == "Fundamentos")["id"]
    json.dumps(c)


def test_to_canvas_units():
    from pipeline.units import Unit

    us = [Unit(1, "Fundamentos"), Unit(2, "Calidad")]
    c = canvas.to_canvas_units("Arq", "arqui", us, {"01-fundamentos": ["Qué es", "Rol"], "02-calidad": []})
    ids = [n["id"] for n in c["nodes"]]
    assert ids == ["root", "u0", "u0h0", "u0h1", "u3"]
    u0 = c["nodes"][1]
    assert u0["file"] == "arqui/unidades/01-fundamentos.md" and u0["x"] == 400 and u0["y"] == 0
    h = c["nodes"][3]
    assert h["file"] == "arqui/unidades/01-fundamentos.md" and h["subpath"] == "#Rol" and h["x"] == 800 and h["y"] == 180
    assert c["nodes"][4]["y"] == 270 and c["nodes"][0]["y"] == 135
    assert {(e["fromNode"], e["toNode"]) for e in c["edges"]} == {("root", "u0"), ("u0", "u0h0"), ("u0", "u0h1"), ("root", "u3")}
    json.dumps(c)
