import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'benchmarks'/'modernization'

def load():
    s=importlib.util.spec_from_file_location('kernel_v4',B/'run_kernel_v4.py')
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def test_protocol_transaction_count_matches_frozen_corpus():
    p=json.loads((B/'kernel_protocol_v1.json').read_text())
    c=json.loads((B/'transaction_corpus.json').read_text())
    assert p['transactions_per_iteration']==len(c['transactions'])

def test_generated_kernels_have_equivalent_clock_boundaries():
    src=load().generate_kernel_sources()
    assert set(src)=={'merit','java','csharp'}
    assert 'monotonic_ns()' in src['merit'] and 'with capability clock' in src['merit']
    assert 'System.nanoTime()' in src['java']
    assert 'Stopwatch.GetTimestamp()' in src['csharp']
    assert src['merit'].index('vec_new<Account>') < src['merit'].index('monotonic_ns()')
    assert src['java'].index('A[]a=fresh()') < src['java'].index('System.nanoTime()')
    assert src['csharp'].index('var a=Fresh()') < src['csharp'].index('Stopwatch.GetTimestamp()')

def test_kernel_v4_executes_three_languages_end_to_end():
    m=load(); report=m.run(); p=m.load_protocol()
    assert report['ranking_eligible'] is True and report['correctness_gate']=='pass'
    impl={x['implementation']:x for x in report['implementations']}
    assert set(impl)=={'merit','java','csharp'}
    assert len({x['checksum'] for x in impl.values()})==1
    assert all(len(x['statistics']['samples_ns'])==p['measured_batches'] for x in impl.values())
