# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `browse.list_projects(program=None)`: list all GDC projects (93
  across ~27 programs — TCGA, TARGET, CPTAC, ALCHEMIST, ...), not
  just data within one already-known project. `gdcfetch projects
  [--program NAME]` on the CLI.
- `list_projects` gained `site`, `disease_type`, and `strategy`
  filters — case-insensitive substring matches against
  `primary_site`, `disease_type`, and the project's experimental
  strategies, respectively (`primary_site` and `disease_type` are
  distinct GDC fields: where vs. what). `gdcfetch projects --site
  --disease-type --strategy` on the CLI.

## [0.1.0] - 2026-08-13

### Added
- Initial release, extracted from `sigmutselcovs`'s GDC client.
- `client`: `search_files`, `download_files`, `download_by_uuid`,
  `get_data_size` (a 1-byte ranged GET for blobs that don't support
  `HEAD` and aren't indexed in `/files`).
- `browse`: faceted discovery (`list_data_categories`,
  `list_data_types`, `list_experimental_strategies`,
  `list_workflow_types`, `describe_project`).
- `auth`: `load_token` / `authenticated_session` for
  controlled-access downloads via GDC's `X-Auth-Token` mechanism
  (dbGaP-authorized researchers only; search never needs a token).
- `presets`: named filters for mutation-signature-relevant data
  (`somatic-mutations` covering SBS/DBS/ID, four copy-number
  variants, `structural-variants` flagged controlled-access) and
  the `gene-expression` covariate.
- `supplementary`: the TCGA ATAC-seq bigWig tarball UUIDs (Corces et
  al. 2018), verified live for all 23 covered cancer types — the
  leading example of GDC-served data that isn't discoverable
  through search at all.
- `manifest`: `gdc-client`-compatible manifest and GDC Data
  Portal-compatible sample sheet writers.
- `gdcfetch` console command: `browse`, `presets`, `search`,
  `download`, `manifest`, `atac`.
