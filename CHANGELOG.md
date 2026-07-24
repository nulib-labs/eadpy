# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is below 1.0.0, breaking changes may appear in minor releases.

## 0.2.0 - Unreleased

### Breaking

- Content marked `audience="internal"` is now **excluded** from parsed output.
  ArchivesSpace exports unpublished records this way when "include unpublished"
  is selected, and repositories use it for internal-use `<dao>` links and
  processing notes, so this content previously appeared in JSON chunks and CSV
  rows. Pass `include_internal=True` to any constructor, or `--include-internal`
  on the command line, to restore the previous behavior. `<eadheader>` and
  `<control>` are exempt from the filter: marking the finding aid's own header
  `audience="internal"` is a common convention, and discarding it would take the
  record identifier with it.
- An `<ead>` root with an unrecognized namespace now raises `EadParseError`
  instead of being parsed as EAD 2002. `EadParseError` subclasses `ValueError`,
  so existing `except ValueError` handlers still catch it.

### Added

- EAD3 (1.1.x) support, detected from the `http://ead3.archivists.org/schema/`
  namespace. EAD3-specific constructs are folded into the existing output shape,
  so downstream consumers need no changes: `<unitdatestructured>` and
  `<physdescstructured>` are read alongside their legacy equivalents
  (ArchivesSpace exports emit both), `<part>` children of name and subject
  elements are joined, `<daoset>` groups are flattened into the digital objects
  list, and `<didnote>` is reported under the same key as EAD 2002 `<note>`.
- Experimental EAD 4.0 support for the draft
  `https://standards.openpreservation.org/ead/v4` schema. The schema is
  unreleased and element mappings may change. Two known limitations: EAD 4.0 has
  no repository element, so `repository` is always `None`, and it has no `<dao>`
  equivalent, so `<reference href="...">` links in a component's own description
  are reported as its digital objects.
- `EAD.ead_version` property reporting the detected version as `"2002"`,
  `"ead3"`, or `"ead4"`. Documents with no namespace fall back to structural
  detection from the root's child elements.
- `include_internal` (keyword-only) on `from_path`, `from_string`, `from_bytes`
  and `from_file`, and `--include-internal` on both CLI subcommands.
- A `DeprecationWarning` when the ignored `encoding` parameter is passed to
  `from_string`. It was previously accepted and silently discarded, which also
  meant `from_string(xml, True)` — a caller meaning `include_internal` — did
  nothing at all.
- Package metadata: license expression, classifiers, and project URLs.

### Fixed

- Whitespace inside element-only content is now collapsed. Finding aids that
  hard-wrap prose leaked raw newlines and tabs into `repository`,
  `extent`/`physdesc`, and note blocks such as `<bioghist>` and
  `<scopecontent>`, which in turn produced multi-line CSV cells.
- Source distributions no longer include local tooling configuration.

## 0.1.4

- Dependency updates and minor bug fixes.

## 0.1.3

- Refactored `EAD` class methods into the public `eadpy` package interface.
- Added `from_path`, `from_string`, `from_bytes` and `from_file` constructors.

## 0.1.2

- Added batch directory processing to the command-line interface.

## 0.1.1

- Added CSV export.

## 0.1.0

- Initial release: EAD 2002 parsing and JSON chunk export.
