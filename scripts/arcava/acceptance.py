#!/usr/bin/env python3
"""PG17 oracle using only a newly created private socket cluster."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BIN = Path('/opt/homebrew/opt/postgresql@17/bin')
PINS = [('001_project_b_baseline_schema.sql','04338b0f8c78c4a97f947996ac72d6cf81a182c75d1f3184ab0a7a0a221e5e36'),('002_project_b_journey_provisioning_hardening.sql','7bd4c9685baf12ccfc02573cdae1c1df0191a6101e41b3d8558dd1621243275a')]

def validate_inventory(items, source_sha):
    if len(source_sha)!=40 or any(c not in '0123456789abcdef' for c in source_sha):
        raise ValueError('malformed_source_metadata')
    if items != PINS:
        raise ValueError('migration_inventory_or_checksum_mismatch')

def main():
    env = {k:v for k,v in os.environ.items() if not k.startswith(('PG','SUPABASE_')) and k!='DATABASE_URL'}
    def run(args, check=True):
        r = subprocess.run(args, env=env, capture_output=True, text=True, timeout=120)
        if check and r.returncode:
            raise RuntimeError(r.stderr)
        return r
    sha = run(['git','-C',str(ROOT),'rev-parse','HEAD']).stdout.strip()
    fixture_path=ROOT/'tests/migration/arcava/A09-T01.case.json'
    fixture=json.loads(fixture_path.read_text())
    code_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    fixture_hash=hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    versions = {n:run([str(BIN/n),'--version']).stdout.strip() for n in ('postgres','psql','pg_ctl','initdb','createdb','pg_config')}
    assert all('17.11' in v for v in versions.values())
    paths = [ROOT/'database/migrations'/n for n,h in PINS]
    validate_inventory(PINS,sha)
    negative_inventory={}
    for label,items,revision in (
        ('missing',PINS[:1],sha),('reorder',list(reversed(PINS)),sha),
        ('duplicate',[PINS[0],PINS[0]],sha),('extra',PINS+[('003.sql','0'*64)],sha),
        ('sha_mismatch',[(PINS[0][0],'0'*64),PINS[1]],sha),
        ('metadata',PINS,'invalid')):
        try:
            validate_inventory(items,revision)
        except ValueError as error:
            negative_inventory[label]={'exit':1,'reason':str(error)}
        else:
            raise AssertionError(label)
    assert {p.name for p in (ROOT/'database/migrations').glob('*.sql')} == {n for n,h in PINS}
    for p,(_,h) in zip(paths,PINS):
        assert not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==h
    temp = Path(tempfile.mkdtemp(prefix='arc-t01-',dir='/private/tmp'))
    temp.chmod(0o700)
    assert temp.resolve().parent==Path('/private/tmp') and temp.stat().st_uid==os.getuid()
    data,sock = temp/'data',temp/'s'
    sock.mkdir(mode=0o700)
    role,port = 'arcava_test_owner','55479'
    receipt = {'source_sha':sha,'versions':versions,'migrations':dict(PINS),'scenarios':{},'commands':[], 'original_T01':'PARTIAL','fixture':'bounded synthetic substitute; full A09-FX-v1 equivalence unproven','admission':'NOT_ADMITTED'}
    receipt['negative_source_inventory']=negative_inventory
    receipt.update({'execution_code_sha256':code_hash,'fixture_sha256':fixture_hash,'fixture_manifest':fixture})
    started=False
    try:
        run([str(BIN/'initdb'),'-D',str(data),'-U',role,'--auth-local=trust','--auth-host=reject'])
        run([str(BIN/'pg_ctl'),'-D',str(data),'-l',str(temp/'log'),'-o',f"-c listen_addresses='' -c unix_socket_directories={sock} -c port={port}",'-w','start'])
        started=True
        def sql(db,text='',files=(),check=True):
            assert db in ('postgres','absent','compatible','conflicting','unknown','rollback')
            args=[str(BIN/'psql'),'-X','-qAt','-v','ON_ERROR_STOP=1','-h',str(sock),'-p',port,'-U',role,'-d',db]
            if files:
                args+=['--single-transaction']
                for p in files: args+=['-f',str(p)]
            else: args+=['-c',text]
            r=run(args,check)
            receipt['commands'].append({'db':db,'sql':text,'files':[str(p).replace(str(temp),'<TMP_ROOT>') for p in files],'exit':r.returncode})
            return r.stdout.strip() if check else r.returncode
        def identity(db):
            v=sql(db,"select current_setting('server_version_num'),current_setting('data_directory'),inet_server_addr() is null,current_database(),current_user").split('|')
            assert 170000<=int(v[0])<180000 and Path(v[1]).resolve()==data.resolve() and v[2:]==['t',db,role]
            receipt.setdefault('target_identities',{})[db]={'server_version_num':v[0],'data_directory':'<TMP_ROOT>/data','socket':'<TMP_ROOT>/s','database':db,'role':role,'inet_server_addr_null':True}
        identity('postgres')
        try:
            sql('external_target','select 1')
        except AssertionError:
            receipt['cross_target_denied_before_connection']=True
        else:
            raise AssertionError('external target accepted')
        receipt['isolation']={'data':'<TMP_ROOT>/data','socket':'<TMP_ROOT>/s','tcp':False,'pid':(data/'postmaster.pid').read_text().splitlines()[0]}
        def snapshot(db):
            c=sql(db,"select n.nspname,c.relname,c.relkind,pg_get_userbyid(c.relowner) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname in ('project_b','arcava_test') order by 1,2,3")
            l=sql(db,'select seq,migration_id,sha256,source_sha from arcava_test.ledger order by seq') if sql(db,"select to_regclass('arcava_test.ledger') is not null")=='t' else ''
            foreign=sql(db,"select n.nspname,c.relname,c.relkind,pg_get_userbyid(c.relowner) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='synthetic_nonowner' order by 1,2,3")+'\n'+sql(db,'select id,payload from synthetic_nonowner.sentinel order by id')
            return {'catalog':c,'ledger':l,'sha256':hashlib.sha256((c+l).encode()).hexdigest(),'nonowner_sha256':hashlib.sha256(foreign.encode()).hexdigest()}
        def plan(db):
            if sql(db,"select to_regclass('arcava_test.ledger') is not null")!='t':
                return {'verdict':'BLOCK_UNKNOWN','reason':'schema_without_approved_ledger','pending':[],'exit':1} if sql(db,"select exists(select 1 from pg_namespace where nspname='project_b')")=='t' else {'verdict':'APPLY_PENDING','reason':'ABSENT','pending':[0,1],'exit':0}
            rows=sql(db,'select seq,migration_id,sha256 from arcava_test.ledger order by seq').splitlines()
            expected=[f'{i+1}|{n}|{h}' for i,(n,h) in enumerate(PINS)]
            if rows!=expected[:len(rows)] or len(rows)>2:
                return {'verdict':'BLOCK_CONFLICTING','reason':'ledger_checksum_or_sequence_mismatch','pending':[],'exit':1}
            return {'verdict':'APPLY_PENDING' if len(rows)<2 else 'SKIP_VERIFIED','reason':'verified_ledger_prefix','pending':list(range(len(rows),2)),'exit':0}
        def apply(db,i):
            n,h=PINS[i]
            ledger=temp/'ledger.sql'
            ledger.write_text("create schema if not exists arcava_test; create table if not exists arcava_test.ledger(seq int primary key,migration_id text unique,sha256 text,applied_at timestamptz default now(),source_sha text,environment text);"+f"insert into arcava_test.ledger(seq,migration_id,sha256,source_sha,environment) values({i+1},'{n}','{h}','{sha}','{db}');")
            sql(db,files=(paths[i],ledger))
        sql('postgres','create role synthetic_foreign_owner nologin')
        for db in ('absent','compatible','conflicting','unknown','rollback'):
            run([str(BIN/'createdb'),'-h',str(sock),'-p',port,'-U',role,db]);identity(db)
            sql(db,"create schema synthetic_nonowner authorization synthetic_foreign_owner; create table synthetic_nonowner.sentinel(id uuid primary key,payload text); alter table synthetic_nonowner.sentinel owner to synthetic_foreign_owner; insert into synthetic_nonowner.sentinel values('00000000-0000-4000-8000-000000000001','synthetic immutable owner sentinel')")
        for db in ('absent','compatible'):
            before=snapshot(db)
            if db=='compatible': apply(db,0)
            verdict=plan(db)
            assert verdict['verdict']=='APPLY_PENDING' and verdict['pending']==([0,1] if db=='absent' else [1])
            for i in verdict['pending']: apply(db,i)
            after=snapshot(db)
            assert len(after['ledger'].splitlines())==2 and 'provisioning_sessions' in after['catalog']
            assert plan(db)['verdict']=='SKIP_VERIFIED' and snapshot(db)==after
            assert before['nonowner_sha256']==after['nonowner_sha256']
            receipt['scenarios'][db]={'expected':'APPLY_PENDING','actual':verdict,'before':before,'after':after,'replay':plan(db)}
        apply('conflicting',0);sql('conflicting',"update arcava_test.ledger set sha256='conflict'")
        sql('unknown','create schema project_b; create table project_b.unrecognized(id int)')
        for db in ('conflicting','unknown'):
            before=snapshot(db)
            expected='BLOCK_CONFLICTING' if db=='conflicting' else 'BLOCK_UNKNOWN'
            verdict=plan(db)
            assert verdict['verdict']==expected and verdict['exit']==1 and snapshot(db)==before
            receipt['scenarios'][db]={'expected':expected,'actual':verdict,'before':before,'after':snapshot(db)}
        bad=temp/'bad.sql';bad.write_text('select 1/0;')
        before=snapshot('rollback')
        rollback_exit=sql('rollback',files=(paths[0],bad),check=False)
        assert rollback_exit!=0 and snapshot('rollback')==before
        receipt['rollback']={'exit':rollback_exit,'before':before,'after':snapshot('rollback')}
        receipt['atomic_rollback']=True
        receipt['result']='LOCAL_MIGRATION_ORACLE_PASS_PARTIAL_FIXTURE'
    finally:
        if started: run([str(BIN/'pg_ctl'),'-D',str(data),'-m','fast','-w','stop'])
        receipt['cleanup']='OWNED_CLUSTER_STOPPED'
        output=ROOT/'docs/arcava/operations/evidence/A09-T01-closure/tests/A09-T01.json'
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(receipt,indent=2)+'\n')
        shutil.rmtree(temp)
    print(receipt['result'])

if __name__=='__main__': main()
