"""Console entry point: the ``gdcfetch`` command.

Subcommands:

- ``projects [--program NAME]`` -- list all GDC projects (TCGA,
  TARGET, CPTAC, ...), optionally narrowed to one program
- ``browse PROJECT`` -- see what data categories/types/strategies exist
- ``presets`` -- list the named query presets
- ``search PROJECT [--preset NAME | --data-type ...]`` -- list matching files
- ``download PROJECT [--preset NAME | --data-type ...] --dest DIR
  [--token-file FILE]`` -- ``--token-file`` is only needed for
  controlled-access presets like ``structural-variants``
- ``manifest PROJECT [--preset NAME | --data-type ...] -o FILE``
- ``atac PROJECT --dest FILE`` -- the TCGA ATAC-seq tarball shortcut
"""

import argparse
import logging
import sys


def _add_project_arg(parser):
    parser.add_argument(
        "project", help="TCGA project id (e.g. TCGA-BRCA)"
    )


def _add_filter_args(parser):
    parser.add_argument(
        "--preset", help="named preset (see `gdcfetch presets`)"
    )
    parser.add_argument("--data-type")
    parser.add_argument("--data-category")
    parser.add_argument("--experimental-strategy")
    parser.add_argument("--workflow-type")
    parser.add_argument(
        "--access", default="open", choices=["open", "controlled"]
    )


def _search_kwargs(args) -> dict:
    if args.preset:
        from .presets import get_preset

        return get_preset(args.preset).search_kwargs()
    return {
        "data_type": args.data_type,
        "data_category": args.data_category,
        "experimental_strategy": args.experimental_strategy,
        "workflow_type": args.workflow_type,
        "access": args.access,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gdcfetch",
        description="Search, browse, and download NCI GDC data",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("projects", help="list all GDC projects")
    p.add_argument(
        "--program", help="narrow to one program, e.g. TCGA"
    )
    p.add_argument(
        "--site",
        help="substring match on primary site, e.g. 'lung'",
    )
    p.add_argument(
        "--disease-type",
        help="substring match on disease type, e.g. 'neoplasms'",
    )
    p.add_argument(
        "--strategy",
        help="substring match on experimental strategy, e.g. 'WGS'",
    )

    p = sub.add_parser(
        "browse", help="see what's available for a project"
    )
    _add_project_arg(p)
    p.add_argument(
        "--data-category",
        help="narrow the data_type listing to one category",
    )

    sub.add_parser("presets", help="list the named query presets")

    p = sub.add_parser("search", help="list matching files")
    _add_project_arg(p)
    _add_filter_args(p)

    p = sub.add_parser("download", help="download matching files")
    _add_project_arg(p)
    _add_filter_args(p)
    p.add_argument("--dest", required=True)
    p.add_argument(
        "--token-file",
        help=(
            "GDC token file (from the Data Portal) for "
            "controlled-access downloads"
        ),
    )

    p = sub.add_parser("manifest", help="write a gdc-client manifest")
    _add_project_arg(p)
    _add_filter_args(p)
    p.add_argument("-o", "--output", required=True)

    p = sub.add_parser(
        "atac",
        help="download the TCGA ATAC-seq tarball for one project",
    )
    p.add_argument("project", help="TCGA code, e.g. BRCA")
    p.add_argument(
        "--dest", required=True, help="output tarball path"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "projects":
        from .browse import list_projects

        hits = list_projects(
            program=args.program,
            site=args.site,
            disease_type=args.disease_type,
            strategy=args.strategy,
        )
        for hit in hits:
            sites = "; ".join(hit.get("primary_site") or [])
            program = hit.get("program", {}).get("name", "")
            print(
                f"{hit['project_id']}\t{program}\t{hit['name']}\t{sites}"
            )
        print(f"# {len(hits)} projects", file=sys.stderr)
        return 0

    if args.command == "browse":
        from .browse import describe_project, list_data_types

        if args.data_category:
            print(f"data types under {args.data_category!r}:")
            for key, count in sorted(
                list_data_types(
                    args.project, data_category=args.data_category
                ).items()
            ):
                print(f"  {key}: {count}")
            return 0
        overview = describe_project(args.project)
        for section, counts in overview.items():
            print(f"{section}:")
            for key, count in sorted(counts.items()):
                print(f"  {key}: {count}")
        return 0

    if args.command == "presets":
        from .presets import list_presets

        for name, preset in sorted(list_presets().items()):
            classes = (
                f" [{', '.join(preset.signature_classes)}]"
                if preset.signature_classes
                else " [covariate]" if preset.is_covariate else ""
            )
            print(f"{name}{classes}: {preset.description}")
            if preset.notes:
                print(f"    {preset.notes}")
        return 0

    if args.command == "search":
        from .client import search_files

        hits = search_files(args.project, **_search_kwargs(args))
        for h in hits:
            print(
                f"{h['file_id']}\t{h['file_name']}\t{h.get('file_size', '')}"
            )
        print(f"# {len(hits)} files", file=sys.stderr)
        return 0

    if args.command == "download":
        from .client import download_files, search_files

        session = None
        if args.token_file:
            from .auth import authenticated_session, load_token

            session = authenticated_session(
                load_token(args.token_file)
            )
        hits = search_files(args.project, **_search_kwargs(args))
        paths = download_files(hits, args.dest, session=session)
        print(f"Downloaded {len(paths)} files to {args.dest}")
        return 0

    if args.command == "manifest":
        from .client import search_files
        from .manifest import write_manifest

        hits = search_files(args.project, **_search_kwargs(args))
        path = write_manifest(hits, args.output)
        print(f"Wrote manifest ({len(hits)} files) to {path}")
        return 0

    if args.command == "atac":
        from .supplementary import download_tcga_atac

        path = download_tcga_atac(args.project, args.dest)
        print(path)
        return 0

    raise AssertionError(f"unhandled command {args.command}")


if __name__ == "__main__":
    sys.exit(main())
