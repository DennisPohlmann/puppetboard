"""Container health check: exit 0 when the status endpoint answers OK."""
import os
import sys
import urllib.request


def url():
    return (f"http://localhost:{os.getenv('PUPPETBOARD_PORT', '8080')}"
            f"{os.getenv('PUPPETBOARD_URL_PREFIX', '')}"
            f"{os.getenv('PUPPETBOARD_STATUS_ENDPOINT', '/status')}")


def main():
    try:
        with urllib.request.urlopen(url(), timeout=4) as response:  # nosec B310
            return 0 if response.status == 200 else 1
    except OSError:
        return 1


if __name__ == '__main__':
    sys.exit(main())
