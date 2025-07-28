def escape_registry_url(i):
    return i.replace("-", "_").replace(".", "_").replace("/", "_")
