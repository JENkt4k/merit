from __future__ import annotations
import argparse, importlib.util, json, math, shutil, statistics, subprocess, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
PROTOCOL=HERE/'kernel_protocol_v1.json'; CORPUS=HERE/'transaction_corpus.json'; SEMANTIC_RUNNER=HERE/'run_comparison_v2.py'
EXPECTED_DIGEST='bf898293d9f9ca33cd0f129ebe314736b5f1e60b7a81bbf55e98205d409b281d'

def money(n:int)->str:
    s='-' if n<0 else ''; n=abs(n); return f'{s}{n//100}.{n%100:02d}'

def load_inputs():
    data=json.loads(CORPUS.read_text()); protocol=json.loads(PROTOCOL.read_text())
    if data.get('schema')!='merit-modernization-transaction-v1': raise ValueError('unsupported corpus')
    if protocol.get('schema')!='merit-modernization-kernel-protocol-v1': raise ValueError('unsupported protocol')
    if protocol['transactions_per_iteration']!=len(data['transactions']): raise ValueError('protocol transaction count differs from frozen corpus')
    return data,protocol

def merit(data,p):
    batches=p['warmup_batches']+p['measured_batches']; n=p['iterations_per_batch']
    accounts='\n'.join(f"                vec_push<Account>(a, Account {{ id:{x['id']}, balance:{money(x['balance_minor'])}, minor:{x['balance_minor']}, seq:{x['last_sequence']} }});" for x in data['accounts'])
    decl='\n'.join(f'                var r{i}:i64=0;' for i,_ in enumerate(data['transactions']))
    tx='\n'.join(f"                    r{i}=apply(a,{t['debit']},{t['credit']},{money(t['amount_minor'])},{t['amount_minor']},{t['sequence']});" for i,t in enumerate(data['transactions']))
    sums='\n'.join(f'                checksum=checked_add(checksum,r{i});' for i,_ in enumerate(data['transactions']))
    return f'''module modernization_kernel
capability allocate; capability clock;
decimal USD(18,2,half_even); bounded AccountNumber(u64,1,999999999999); bounded Sequence(u64,0,9999999999999999999);
struct Account {{ id:AccountNumber; balance:USD; minor:i64; seq:Sequence; }}
fn find(borrow a:Vec<Account>,id:AccountNumber)->i64 {{ var i:i64=0; while(i<vec_len<Account>(a)){{ let x:Account=vec_get<Account>(a,i); if(x.id==id){{return i;}} i=checked_add(i,1); }} return -1; }}
fn apply(borrow_mut a:Vec<Account>,d:AccountNumber,c:AccountNumber,amount:USD,minor:i64,seq:Sequence)->i64 {{
 if(amount<=0.00){{return 1;}} if(d==c){{return 2;}} let di:i64=find(a,d); if(di<0){{return 3;}} let ci:i64=find(a,c); if(ci<0){{return 4;}}
 let debit:Account=vec_get<Account>(a,di); let credit:Account=vec_get<Account>(a,ci); if(seq<=debit.seq){{return 5;}} if(seq<=credit.seq){{return 5;}} if(debit.balance<amount){{return 6;}} if(credit.balance>{money(data['max_balance_minor'])}-amount){{return 7;}}
 var nd:Account=debit; nd.balance=checked_sub(nd.balance,amount); nd.minor=checked_sub(nd.minor,minor); nd.seq=seq;
 var nc:Account=credit; nc.balance=checked_add(nc.balance,amount); nc.minor=checked_add(nc.minor,minor); nc.seq=seq; vec_set<Account>(a,di,nd); vec_set<Account>(a,ci,nc); return 0;
}}
fn main()->i32 {{ with capability allocate {{ let alloc:Allocator=system_allocator(); var batch:i64=0; while(batch<{batches}){{ var elapsed:i64=0; var checksum:i64=0; var it:i64=0; while(it<{n}){{ var a:Vec<Account>=vec_new<Account>(alloc,{len(data['accounts'])});
{accounts}
{decl}
                with capability clock {{ let before:i64=monotonic_ns();
{tx}
                    let after:i64=monotonic_ns(); elapsed=checked_add(elapsed,checked_sub(after,before)); }}
{sums}
                var j:i64=0; while(j<vec_len<Account>(a)){{ let x:Account=vec_get<Account>(a,j); checksum=checked_add(checksum,x.minor/1000003); j=checked_add(j,1); }} drop(a); it=checked_add(it,1); }}
            print("KERNEL"); print(elapsed); print(checksum); batch=checked_add(batch,1); }} }} return 0; }}
'''

def java(data,p):
    batches=p['warmup_batches']+p['measured_batches']; n=p['iterations_per_batch']
    ac=',\n'.join(f'new A({x["id"]}L,new BigDecimal("{money(x["balance_minor"])}"),{x["balance_minor"]}L,{x["last_sequence"]}L)' for x in data['accounts'])
    amounts='\n'.join(f'static final BigDecimal M{i}=new BigDecimal("{money(t["amount_minor"])}");' for i,t in enumerate(data['transactions']))
    tx='\n'.join(f'int r{i}=apply(a,{t["debit"]}L,{t["credit"]}L,M{i},{t["amount_minor"]}L,{t["sequence"]}L);' for i,t in enumerate(data['transactions']))
    sums=''.join(f' checksum+=r{i};' for i,_ in enumerate(data['transactions']))
    return f'''import java.math.BigDecimal;
public final class ModernizationKernel{{ static final BigDecimal Z=new BigDecimal("0.00"),MAX=new BigDecimal("{money(data['max_balance_minor'])}"); {amounts}
 static final class A{{final long id;BigDecimal b;long minor,seq;A(long i,BigDecimal b,long m,long s){{id=i;this.b=b;minor=m;seq=s;}}}}
 static A[] fresh(){{return new A[]{{{ac}}};}} static int find(A[]a,long id){{for(int i=0;i<a.length;i++)if(a[i].id==id)return i;return -1;}}
 static int apply(A[]a,long d,long c,BigDecimal m,long minor,long s){{if(m.compareTo(Z)<=0)return 1;if(d==c)return 2;int di=find(a,d);if(di<0)return 3;int ci=find(a,c);if(ci<0)return 4;A x=a[di],y=a[ci];if(s<=x.seq||s<=y.seq)return 5;if(x.b.compareTo(m)<0)return 6;if(y.b.compareTo(MAX.subtract(m))>0)return 7;x.b=x.b.subtract(m);x.minor-=minor;y.b=y.b.add(m);y.minor+=minor;x.seq=s;y.seq=s;return 0;}}
 public static void main(String[]z){{for(int batch=0;batch<{batches};batch++){{long elapsed=0,checksum=0;for(int it=0;it<{n};it++){{A[]a=fresh();long before=System.nanoTime();{tx} long after=System.nanoTime();elapsed+=after-before;{sums} for(A x:a)checksum+=x.minor/1000003L;}}System.out.println("KERNEL");System.out.println(elapsed);System.out.println(checksum);}}}}
}}
'''

def csharp(data,p):
    batches=p['warmup_batches']+p['measured_batches']; n=p['iterations_per_batch']
    ac=',\n'.join(f'new A({x["id"]}L,{money(x["balance_minor"])}m,{x["balance_minor"]}L,{x["last_sequence"]}L)' for x in data['accounts'])
    tx='\n'.join(f'var r{i}=Apply(a,{t["debit"]}L,{t["credit"]}L,{money(t["amount_minor"])}m,{t["amount_minor"]}L,{t["sequence"]}L);' for i,t in enumerate(data['transactions']))
    sums=''.join(f' checksum+=r{i};' for i,_ in enumerate(data['transactions']))
    return f'''using System;using System.Diagnostics;
internal static class ModernizationKernel{{const decimal Max={money(data['max_balance_minor'])}m;sealed class A{{internal readonly long Id;internal decimal B;internal long Minor,Seq;internal A(long i,decimal b,long m,long s){{Id=i;B=b;Minor=m;Seq=s;}}}}static A[] Fresh()=>new A[]{{{ac}}};static int Find(A[]a,long id){{for(var i=0;i<a.Length;i++)if(a[i].Id==id)return i;return -1;}}static int Apply(A[]a,long d,long c,decimal m,long minor,long s){{if(m<=0m)return 1;if(d==c)return 2;var di=Find(a,d);if(di<0)return 3;var ci=Find(a,c);if(ci<0)return 4;var x=a[di];var y=a[ci];if(s<=x.Seq||s<=y.Seq)return 5;if(x.B<m)return 6;if(y.B>Max-m)return 7;checked{{x.B-=m;x.Minor-=minor;y.B+=m;y.Minor+=minor;}}x.Seq=s;y.Seq=s;return 0;}}public static int Main(){{for(var batch=0;batch<{batches};batch++){{long elapsed=0,checksum=0;for(var it=0;it<{n};it++){{var a=Fresh();var before=Stopwatch.GetTimestamp();{tx}var after=Stopwatch.GetTimestamp();elapsed+=(long)((after-before)*(1_000_000_000.0/Stopwatch.Frequency));{sums}foreach(var x in a)checksum+=x.Minor/1000003L;}}Console.WriteLine("KERNEL");Console.WriteLine(elapsed);Console.WriteLine(checksum);}}return 0;}}}}
'''

def generate_kernel_sources():
    d,p=load_inputs(); return {'merit':merit(d,p),'java':java(d,p),'csharp':csharp(d,p)}

def _module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f'cannot import {path}')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def percentile(values,p):
    o=sorted(values); return o[max(0,math.ceil(p*len(o))-1)]

def stats(values,operations):
    median=int(statistics.median(values)); return {'samples_ns':values,'median_ns':median,'p95_ns':percentile(values,.95),'mad_ns':int(statistics.median(abs(v-median) for v in values)),'minimum_ns':min(values),'maximum_ns':max(values),'transactions_per_second_at_median':operations*1_000_000_000.0/median}

def load_protocol():
    p=json.loads(PROTOCOL.read_text()); c=json.loads(CORPUS.read_text())
    if p.get('schema')!='merit-modernization-kernel-protocol-v1' or p.get('ranking_eligible') is not True or p.get('correctness_gate_required') is not True: raise ValueError('invalid kernel protocol')
    if p['transactions_per_iteration']!=len(c['transactions']): raise ValueError('kernel protocol transaction count differs from frozen corpus')
    return p

def parse_kernel_line(stdout):
    marker=[x.strip() for x in stdout.splitlines() if x.strip().startswith('KERNEL,')]
    if len(marker)!=1: raise AssertionError('kernel executable must emit exactly one KERNEL marker')
    parts=marker[0].split(',')
    if len(parts)!=3: raise AssertionError('invalid KERNEL marker')
    elapsed,checksum=map(int,parts[1:])
    if elapsed<=0 or checksum==0: raise AssertionError('invalid kernel timing/checksum')
    return elapsed,checksum

def parse_kernel_output(stdout,expected_batches):
    lines=[x.strip() for x in stdout.splitlines() if x.strip()]; records=[]
    if len(lines)%3: raise AssertionError('invalid kernel output field count')
    for i in range(0,len(lines),3):
        if lines[i]!='KERNEL': raise AssertionError('invalid kernel marker')
        elapsed,checksum=int(lines[i+1]),int(lines[i+2])
        if elapsed<=0 or checksum==0: raise AssertionError('invalid kernel timing/checksum')
        records.append((elapsed,checksum))
    if len(records)!=expected_batches: raise AssertionError(f'kernel executable emitted {len(records)} batches; expected {expected_batches}')
    if len({c for _,c in records})!=1: raise AssertionError('kernel checksum changed between batches')
    return records

def report_from_samples(samples,checksums,protocol=None):
    p=protocol or load_protocol(); expected={'merit','java','csharp'}
    if set(samples)!=expected or set(checksums)!=expected: raise AssertionError('kernel report requires Merit, Java and C#')
    if len(set(checksums.values()))!=1: raise AssertionError('kernel checksums disagree across implementations')
    ops=p['iterations_per_batch']*p['transactions_per_iteration']; measured=p['measured_batches']; impl=[]
    for name in ('merit','java','csharp'):
        if len(samples[name])!=measured: raise AssertionError(f'{name} sample count differs from protocol')
        impl.append({'implementation':name,'semantic_digest':EXPECTED_DIGEST,'checksum':checksums[name],'statistics':stats(samples[name],ops)})
    return {'schema':'merit-modernization-kernel-report-v4','protocol_schema':p['schema'],'measurement':p['measurement'],'ranking_eligible':True,'correctness_gate':'pass','clock_scope':p['clock_scope'],'state_reset':p['state_reset'],'anti_optimization':p['anti_optimization'],'warmup_batches_discarded':p['warmup_batches'],'implementations':impl}

def _run(cmd): return subprocess.run(cmd,text=True,capture_output=True,check=True).stdout

def _build_and_run(p,work):
    from merit.project.build import build
    from merit.project.loader import load_project
    src=generate_kernel_sources(); batches=p['warmup_batches']+p['measured_batches']
    merit_dir=work/'merit'; (merit_dir/'src').mkdir(parents=True); (merit_dir/'src/main.mrt').write_text(src['merit']); (merit_dir/'Merit.toml').write_text('[package]\nname="modernization_kernel"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n\n[build]\nc_flags=["-O2"]\n')
    _,_,exe=build(load_project(merit_dir/'Merit.toml'),work/'merit-out'); result={'merit':parse_kernel_output(_run([str(exe)]),batches)}
    javac,java_cmd=shutil.which('javac'),shutil.which('java')
    if not javac or not java_cmd: raise RuntimeError('kernel benchmark requires javac and java')
    j=work/'java'; j.mkdir(); (j/'ModernizationKernel.java').write_text(src['java']); out=work/'java-out'; out.mkdir(); subprocess.run([javac,'-d',str(out),str(j/'ModernizationKernel.java')],check=True,capture_output=True,text=True); result['java']=parse_kernel_output(_run([java_cmd,'-cp',str(out),'ModernizationKernel']),batches)
    dotnet=shutil.which('dotnet')
    if not dotnet: raise RuntimeError('kernel benchmark requires dotnet SDK 8+')
    cs=work/'csharp'; cs.mkdir(); (cs/'ModernizationKernel.cs').write_text(src['csharp']); (cs/'ModernizationKernel.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>disable</ImplicitUsings><InvariantGlobalization>true</InvariantGlobalization><AssemblyName>ModernizationKernel</AssemblyName></PropertyGroup></Project>')
    co=work/'csharp-out'; subprocess.run([dotnet,'build',str(cs/'ModernizationKernel.csproj'),'-c','Release','-o',str(co),'--nologo','-v:q'],check=True,capture_output=True,text=True); result['csharp']=parse_kernel_output(_run([dotnet,str(co/'ModernizationKernel.dll')]),batches)
    return result

def run():
    p=load_protocol(); semantic=_module('semantic_gate',SEMANTIC_RUNNER).run()
    if semantic['outcome_sha256']!=EXPECTED_DIGEST or any(x['correctness']!='pass' for x in semantic['implementations']): raise AssertionError('semantic correctness gate failed')
    with tempfile.TemporaryDirectory(prefix='merit-kernel-v4-') as tmp: records=_build_and_run(p,Path(tmp))
    w=p['warmup_batches']; samples={k:[e for e,_ in v[w:]] for k,v in records.items()}; checksums={k:v[0][1] for k,v in records.items()}; return report_from_samples(samples,checksums,p)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--json',action='store_true'); args=ap.parse_args(); r=run()
    if args.json: print(json.dumps(r,sort_keys=True,separators=(',',':')))
    else:
        print(f"schema: {r['schema']}\ncorrectness gate: pass")
        for x in r['implementations']:
            s=x['statistics']; print(f"{x['implementation']}: median_ns={s['median_ns']} p95_ns={s['p95_ns']} tx/s={s['transactions_per_second_at_median']:.2f} checksum={x['checksum']}")
    return 0
if __name__=='__main__': raise SystemExit(main())