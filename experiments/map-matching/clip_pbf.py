"""Clip a .osm.pbf to a bbox: ways with a node inside, all their nodes, and
relations whose members were kept (two passes, pyosmium)."""
import sys
import osmium

src, dst, w, s, e, n = sys.argv[1], sys.argv[2], *map(float, sys.argv[3:7])
inside = lambda loc: w <= loc.lon <= e and s <= loc.lat <= n

way_ids, node_ids = set(), set()
for obj in osmium.FileProcessor(src, osmium.osm.NODE | osmium.osm.WAY).with_locations():
    if obj.is_way():
        refs = [nd.ref for nd in obj.nodes]
        if any(nd.location.valid() and inside(nd.location) for nd in obj.nodes):
            way_ids.add(obj.id)
            node_ids.update(refs)
    elif obj.is_node() and inside(obj.location):
        node_ids.add(obj.id)

writer = osmium.SimpleWriter(dst, overwrite=True)
kept = {"n": 0, "w": 0, "r": 0}
for obj in osmium.FileProcessor(src):
    if obj.is_node() and obj.id in node_ids:
        writer.add_node(obj); kept["n"] += 1
    elif obj.is_way() and obj.id in way_ids:
        writer.add_way(obj); kept["w"] += 1
    elif obj.is_relation() and any(
        (m.type == "w" and m.ref in way_ids) or (m.type == "n" and m.ref in node_ids) for m in obj.members
    ):
        writer.add_relation(obj); kept["r"] += 1
writer.close()
print(kept)
