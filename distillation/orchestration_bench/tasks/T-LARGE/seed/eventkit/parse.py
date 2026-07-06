def parse_line(line):
    """Parse one 'k=v k=v' log line into a dict. TODO: coerce values by the registry."""
    out = {}
    for tok in line.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k] = v   # TODO: coerce via registry
    return out
