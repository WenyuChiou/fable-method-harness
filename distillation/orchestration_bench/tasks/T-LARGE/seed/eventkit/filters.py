def match(event, field, value):
    """Return True if event[field] == value. TODO: decide unknown-field behavior."""
    return event.get(field) == value
