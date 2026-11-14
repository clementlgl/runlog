"""Walkable OSM network for a bbox, from a local .osm.pbf (no Overpass)."""

from xml.sax.saxutils import quoteattr

import osmium
import osmnx as ox
from mappymatch.maps.nx.nx_map import NetworkType, NxMap
from mappymatch.maps.nx.readers.osm_readers import parse_osmnx_graph

# Ways a runner can use. Motorways/trunks excluded; access/foot restrictions below.
WALKABLE = {
    "footway", "path", "track", "pedestrian", "steps", "bridleway", "cycleway",
    "living_street", "residential", "unclassified", "service", "tertiary",
    "tertiary_link", "secondary", "secondary_link", "primary", "primary_link", "road",
}


def _walkable(tags) -> bool:
    if tags.get("highway") not in WALKABLE:
        return False
    if tags.get("foot") in ("no", "private") or tags.get("access") in ("no", "private"):
        return tags.get("foot") in ("yes", "designated", "permissive")
    return tags.get("area") != "yes"


def extract_xml(pbf: str, bbox: tuple[float, float, float, float], out: str) -> int:
    """Write walkable ways touching ``bbox`` (west, south, east, north) and their
    nodes to an .osm XML file osmnx can read. Returns the number of ways."""
    w, s, e, n = bbox
    nodes: dict[int, tuple[float, float]] = {}
    ways: list[tuple[int, list[int], dict]] = []
    fp = osmium.FileProcessor(pbf, osmium.osm.NODE | osmium.osm.WAY).with_locations()
    for obj in fp:
        if not obj.is_way() or not _walkable(obj.tags):
            continue
        locs = [(nd.ref, nd.location) for nd in obj.nodes if nd.location.valid()]
        if not any(w <= loc.lon <= e and s <= loc.lat <= n for _, loc in locs):
            continue
        for ref, loc in locs:
            nodes[ref] = (loc.lat, loc.lon)
        ways.append((obj.id, [ref for ref, _ in locs], {t.k: t.v for t in obj.tags}))
    with open(out, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6">\n')
        for ref, (lat, lon) in nodes.items():
            f.write(f'<node id="{ref}" lat="{lat}" lon="{lon}"/>\n')
        for wid, refs, tags in ways:
            f.write(f'<way id="{wid}">')
            f.writelines(f'<nd ref="{r}"/>' for r in refs)
            f.writelines(f"<tag k={quoteattr(k)} v={quoteattr(v)}/>" for k, v in tags.items())
            f.write("</way>\n")
        f.write("</osm>\n")
    return len(ways)


def nx_map_from_xml(path: str) -> NxMap:
    raw = ox.graph_from_xml(path, simplify=True, retain_all=False)
    return NxMap(parse_osmnx_graph(raw, NetworkType.WALK, xy=True))
