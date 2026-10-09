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
