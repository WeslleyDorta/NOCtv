# Third-party notices

NOCtv source code is MIT licensed. Dependencies and assets retain their own licenses.

- **Geist / Geist Mono:** Copyright 2023 Vercel, in collaboration with
  basement.studio. SIL Open Font License 1.1; complete text is in
  `web/fonts/LICENSE-Geist.txt`.
- **Brand SVGs:** Simple Icons, CC0. Exact upstream revision, per-file hash and
  brand source links are in [docs/brands.md](docs/brands.md). These are identifiers,
  not sponsorship claims. Trademark rights are separate from copyright licensing.
- **Gunicorn:** MIT; installed from PyPI by `requirements.txt`.
- **packaging:** Apache-2.0 OR BSD-2-Clause; installed from PyPI.
- **Playwright:** Apache-2.0; development/browser checks only.
- **Country outlines:** Natural Earth, public domain. Pinned source and
  reproduction steps are in [docs/maps.md](docs/maps.md).

- **Brazil federative units:** IBGE simplified Malhas API v3 geometry. Source,
  transformation and snapshot hash are documented in [docs/maps.md](docs/maps.md).

No manufacturer faceplates, private screenshots, device-export images or other
operational media are distributed. Generic device/interface drawings are part
of the NOCtv source.

The Docker image also installs distribution packages `iputils-ping`, `traceroute`,
`dnsutils` and `nmap` with their dependencies. These retain their upstream licenses,
including Nmap's license; they are not relicensed under NOCtv's MIT license.
Installed copyright/license notices remain under `/usr/share/doc/` in the image.
Consult those package notices and [Nmap licensing](https://nmap.org/book/man-legal.html)
before redistributing an image under different commercial terms.
