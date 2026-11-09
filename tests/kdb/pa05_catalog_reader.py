"""PA-05 test-only adapter. Docker-local fixture access; not an authenticated API."""
import json
import re
import subprocess
import uuid


def read_catalog(container, version, tenant, subject, purpose):
    """Fail closed with no candidate on malformed context, SQL failure or no row."""
    if not isinstance(container, str) or not re.fullmatch(r'kdb-pa05-[0-9a-f]{12}', container):
        return {'status': 'DENY', 'candidate': None}
    try:
        version = str(uuid.UUID(version))
        values = (tenant, subject, purpose)
        if any(not isinstance(v, str) or not v or len(v) > 128 for v in values):
            raise ValueError('invalid context')
        quoted = ["'" + v.replace("'", "''") + "'" for v in values]
        query = "SELECT pa05_test.read_catalog('{}',{},{},{});".format(version, *quoted)
        p = subprocess.run(['docker', 'exec', '-i', container, 'psql', '-X', '-qAt',
                            '-v', 'ON_ERROR_STOP=1', '-U', 'pa05_fixture_reader', '-d', 'postgres'],
                           input=query, text=True, capture_output=True, timeout=10)
        if p.returncode or not p.stdout.strip():
            return {'status': 'DENY', 'candidate': None}
        result = json.loads(p.stdout)
        if not isinstance(result, dict):
            raise ValueError('invalid result')
        return {'status': 'SYNTHETIC_READ', 'candidate': result}
    except (ValueError, TypeError, OSError, subprocess.TimeoutExpired):
        return {'status': 'DENY', 'candidate': None}
