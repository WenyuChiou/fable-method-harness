import sys
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    # TODO: subcommands: ingest, query, version
    print("eventkit")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
