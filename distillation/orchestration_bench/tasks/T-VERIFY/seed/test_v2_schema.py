import glob, yaml
def test_all_v2():
    bad = []
    for f in sorted(glob.glob("configs/config_*.yaml")):
        d = yaml.safe_load(open(f, encoding="utf-8"))
        if not isinstance(d.get("retry"), dict):   # v2 has nested retry
            bad.append(f)
    assert not bad, f"non-v2 configs: {bad}"
