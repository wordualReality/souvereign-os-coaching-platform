"""PD01 test-only adapter. Docker-local fixture access; not an authenticated API."""
import json
import re
import subprocess
import uuid

REQUIRED_SNAPSHOT_KEYS = {'schemaVersion', 'synthetic', 'title', 'instructions'}


def snapshot_schema_ok(snapshot):
    """Fail closed unless the snapshot matches the frozen PD01 detail schema types."""
    if not isinstance(snapshot, dict) or set(snapshot) != REQUIRED_SNAPSHOT_KEYS:
        return False
    if snapshot.get('schemaVersion') != 'PD01_DETAIL_TEST_ONLY_V1':
        return False
    if snapshot.get('synthetic') is not True:
        return False
    title = snapshot.get('title')
    if not isinstance(title, str) or not (1 <= len(title) <= 128):
        return False
    instructions = snapshot.get('instructions')
    if not isinstance(instructions, list) or not (1 <= len(instructions) <= 8):
        return False
    return all(isinstance(item, str) and 1 <= len(item) <= 256 for item in instructions)


def read_detail(container, version, tenant, subject, purpose):
    """Fail closed with no detail on malformed context, SQL failure or no row."""
    if not isinstance(container, str) or not re.fullmatch(r'kdb-pd01-[0-9a-f]{12}', container):
        return {'status': 'DENY', 'candidate': None}
    try:
        version = str(uuid.UUID(str(version)))
        values = (tenant, subject, purpose)
        if any(not isinstance(v, str) or not v or len(v) > 128 for v in values):
            raise ValueError('invalid context')
        quoted = ["'" + v.replace("'", "''") + "'" for v in values]
        query = "SELECT pd01_test.read_detail('{}',{},{},{});".format(version, *quoted)
        p = subprocess.run(['docker', 'exec', '-i', container, 'psql', '-X', '-qAt',
                            '-v', 'ON_ERROR_STOP=1', '-U', 'pd01_fixture_reader', '-d', 'postgres'],
                           input=query, text=True, capture_output=True, timeout=10)
        if p.returncode or not p.stdout.strip():
            return {'status': 'DENY', 'candidate': None}
        result = json.loads(p.stdout)
        if not isinstance(result, dict) or not result.get('title') or not result.get('instruction'):
            raise ValueError('invalid result')
        if not snapshot_schema_ok(result.get('canonicalSnapshot')):
            raise ValueError('invalid snapshot schema')
        if result.get('title') != result['canonicalSnapshot']['title']:
            raise ValueError('title mismatch')
        if result.get('instruction') != result['canonicalSnapshot']['instructions'][0]:
            raise ValueError('instruction mismatch')
        return {'status': 'SYNTHETIC_READ', 'candidate': result}
    except (ValueError, TypeError, OSError, subprocess.TimeoutExpired, IndexError, KeyError):
        return {'status': 'DENY', 'candidate': None}
