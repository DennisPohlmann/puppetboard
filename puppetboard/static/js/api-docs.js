// Scalar API reference for /api/v1/docs: read-only, nothing loaded from outside.
// No #api-reference or data-spec* markup: standalone.js would mount a second copy with defaults.
(function () {
  var stored = localStorage.getItem('theme');
  var dark = stored ? stored === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
  var el = document.getElementById('api-docs');
  Scalar.createApiReference(el, {
    url: el.dataset.openapi,
    forceDarkModeState: dark ? 'dark' : 'light',
    hideDarkModeToggle: true,
    hideClientButton: true,
    hideTestRequestButton: true,
    withDefaultFonts: false,
    telemetry: false,
    showDeveloperTools: 'never',
    agent: { disabled: true },
    mcp: { disabled: true },
    documentDownloadType: 'json'
  });
})();
