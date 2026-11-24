# Third-party components

Puppetboard is licensed under the Apache License 2.0 (see `LICENSE`). It ships
the following third-party files under `puppetboard/static/`. Their licenses
are compatible with Apache-2.0; the full texts are at the linked URLs.

| Component | Version | License | Source |
|---|---|---|---|
| jQuery | 4.1.0 | MIT | https://jquery.com/license/ |
| Fomantic-UI | 2.9.4 | MIT | https://github.com/fomantic/Fomantic-UI/blob/develop/LICENSE.md |
| Fomantic-UI icon fonts (Font Awesome Free) | 2.9.4 | Fonts: SIL OFL 1.1, icons: CC BY 4.0 | https://fontawesome.com/license/free |
| Lato font (bundled with Fomantic-UI and in `fonts/lato`) | | SIL OFL 1.1 | https://fonts.google.com/specimen/Lato/license |
| Open Sans font (`fonts/open-sans`) | | SIL OFL 1.1 | https://fonts.google.com/specimen/Open+Sans/license |
| Cousine font (`fonts/cousine`) | | Apache-2.0 | https://fonts.google.com/specimen/Cousine/license |
| DataTables | 3.1.6 | MIT | https://datatables.net/license/ |
| DataTables Buttons | 4.1.3 | MIT | https://datatables.net/license/ |
| billboard.js (includes D3, ISC) | 4.1.5 | MIT | https://github.com/naver/billboard.js/blob/master/LICENSE |
| Moment.js | 2.31.0 | MIT | https://github.com/moment/moment/blob/develop/LICENSE |
| Scalar API Reference (`libs/scalar/standalone.js`, includes Vue and other MIT/ISC/BSD code) | 1.83.0 | MIT | https://github.com/scalar/scalar/blob/main/LICENSE |
| JSZip | 3.10.2 | MIT (dual MIT/GPLv3, used under MIT) | https://github.com/Stuk/jszip/blob/main/LICENSE.markdown |

Python dependencies are installed from PyPI and not shipped in this
repository. All of them use permissive licenses (MIT, BSD, Apache-2.0,
PSF-2.0, MIT-0) except `certifi` (MPL-2.0, used unmodified). Test-only tools
such as `pylint` (GPL-2.0) are not part of the application.
