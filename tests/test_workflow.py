"""Host checks and an independent TTL-subset model, not camera emulation."""
import sys,re,shlex,tempfile,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import gr3_workflow as w
from PIL import Image

class Model:
    def __init__(self,files,fail=None):self.files=dict(files);self.handles={};self.vars={'result':0};self.fail=fail;self.writes=[]
    def value(self,text):
        try:return int(text)
        except ValueError:return self.vars.get(text,0)
    def run(self,script):
        lines=script.decode('ascii').splitlines();labels={x[1:]:i for i,x in enumerate(lines) if x.startswith(':')};pc=0
        while pc<len(lines):
            line=lines[pc];pc+=1
            if line.startswith('if '):
                a,op,b=re.fullmatch(r'if (\w+) (=|<>|<|>|<=|>=) (-?\w+) then',line).groups();av=self.value(a);bv=self.value(b)
                ok={'=':av==bv,'<>':av!=bv,'<':av<bv,'>':av>bv,'<=':av<=bv,'>=':av>=bv}[op]
                if not ok:
                    depth=1
                    while depth:
                        x=lines[pc];pc+=1
                        if x.startswith('if '):depth+=1
                        elif x=='endif':depth-=1
                continue
            if line=='exit':break
            if line=='endif' or line.startswith(':'):continue
            if line.startswith('goto '):pc=labels[line[5:]];continue
            if re.fullmatch(r'\w+ = -?\w+',line):a,b=line.split(' = ');self.vars[a]=self.value(b);continue
            # shlex posix=False preserves backslashes inside quoted Windows paths.
            x=shlex.split(line,posix=False);x=[v[1:-1] if v.startswith("'") and v.endswith("'") else v for v in x];op=x[0]
            if op=='filestat':self.vars[x[2]]=len(self.files.get(x[1],b''));self.vars['result']=0 if x[1] in self.files else -1
            elif op=='getfileattr':self.vars['result']=32 if x[1] in self.files else -1
            elif op=='filecopy':
                if x[2]==self.fail:self.fail=None;continue
                if x[1] in self.files:self.files[x[2]]=self.files[x[1]];self.writes.append(x[2])
            elif op in ['fileopen','filecreate']:
                path=x[2]
                if op=='filecreate':self.files[path]=b''
                if path not in self.files:self.vars[x[1]]=-1
                else:self.vars[x[1]]=len(self.handles)+1;self.handles[self.vars[x[1]]]=[path,len(self.files[path]) if op=='fileopen' and x[3]=='1' else 0]
            elif op=='fileclose':pass
            elif op=='filetruncate':self.files[x[1]]=self.files[x[1]][:int(x[2])].ljust(int(x[2]),b'\0')
            elif op=='fileseek':self.handles[self.vars[x[1]]][1]=int(x[2])
            elif op in ['filewrite','filewriteln']:
                path,pos=self.handles[self.vars[x[1]]]
                if op=='filewrite':data=bytes(map(int,re.findall(r'#(\d+)',line)))
                else:data=(x[2] if line.split()[2].startswith("'") else str(self.vars[x[2]])).encode('ascii')+b'\r\n'
                old=self.files[path];self.files[path]=old[:pos]+data+old[pos+len(data):];self.handles[self.vars[x[1]]][1]+=len(data)
            elif op=='int2str':self.vars[x[1]]=str(self.vars[x[2]])
            else:raise AssertionError('Unhandled '+line)
        return self

def combined(candidate,n):
    a=w.stage_script(candidate,n).replace(b'goto done',b'goto stage_done').replace(b':done',b':stage_done')
    return a[:-6]+b'if error <> 0 then\r\nexit\r\nendif\r\n'+w.install_script(n)

class WorkflowTests(unittest.TestCase):
    def setUp(self):self.n=w.names('A123');self.payload=bytes((i*31)%256 for i in range(w.SIZE));self.original=b'O'*w.SIZE
    def files(self):return {w.TARGET:self.original,'C:\\'+self.n['log1']:b'','C:\\'+self.n['log2']:b''}
    def test_export_no_internal_writes(self):
        m=Model({w.TARGET:self.original}).run(w.export_script());self.assertTrue(m.writes);self.assertTrue(all(p.startswith('C:') for p in m.writes));self.assertEqual(m.files['C:\\G3READ1.JPG'],self.original)
    def test_stage_preserves_target_and_reconstructs_zero_bytes(self):
        m=Model(self.files()).run(w.stage_script(self.payload,self.n));self.assertEqual(m.files[w.TARGET],self.original);self.assertEqual(m.files[self.n['temporary']],self.payload);self.assertEqual(m.files[self.n['backup']],self.original)
    def test_combined_install_and_repeated_boot(self):
        s=combined(self.payload,self.n);w.audit(s,self.payload);m=Model(self.files()).run(s);self.assertEqual(m.files[w.TARGET],self.payload);self.assertEqual(m.files['C:\\'+self.n['final']],self.payload)
        previous=m.files.copy();m.run(s);self.assertEqual(m.files,previous)
    def test_failed_backup_blocks_target_write(self):
        m=Model(self.files(),fail=self.n['backup']).run(combined(self.payload,self.n));self.assertEqual(m.files[w.TARGET],self.original);self.assertNotIn(self.n['temporary'],m.files)
    def test_existing_temporary_is_not_overwritten(self):
        f=self.files();f[self.n['temporary']]=b'keep';m=Model(f).run(combined(self.payload,self.n));self.assertEqual(m.files[w.TARGET],self.original);self.assertEqual(m.files[self.n['temporary']],b'keep')
    def test_missing_final_readback_attempts_rollback(self):
        m=Model(self.files(),fail='C:\\'+self.n['final']).run(combined(self.payload,self.n));self.assertEqual(m.files[w.TARGET],self.original);self.assertEqual(m.files['C:\\'+self.n['rollback']],self.original)
    def test_restore_uses_saved_previous(self):
        s,log,out=w.restore_script(self.n,'A123');m=Model({w.TARGET:self.payload,self.n['backup']:self.original,'C:\\'+log:b''}).run(s);self.assertEqual(m.files[w.TARGET],self.original)
    def test_empty_and_duplicate_logs_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'log';p.write_bytes(b'')
            with self.assertRaises(ValueError):w.read_log(p)
            p.write_text('error\n0\nerror\n0\n')
            with self.assertRaises(ValueError):w.read_log(p)
    def test_invalid_tokens_rejected(self):
        for token in ['../../','a123','123456','ABC\n']:
            with self.assertRaises(ValueError):w.names(token)
    def test_manifest_path_injection_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);m={'model':'GR III','firmware':'2.10','token':'A123','names':self.n.copy()};m['names']['temporary']='bad';w.save_manifest(p,m)
            with self.assertRaises(ValueError):w.load_manifest(p)
    def test_final_hash_checked_even_when_log_success(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);package=p/'package';package.mkdir();card=p/'card';card.mkdir();w.save_manifest(package,{'model':'GR III','firmware':'2.10','token':'A123','names':self.n,'candidate_sha256':w.sha(self.payload)})
            (card/self.n['log2']).write_text('started\n1\nwrite_started\n1\ninstalled_readback_saved\n1\nerror\n0\nattempted\n1\nrestored\n0\ncompleted\n1\n');(card/self.n['final']).write_bytes(self.original)
            with self.assertRaises(ValueError):w.verify_install(package,card)
    def test_layout_reserves_lower_band(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'source.png';Image.new('RGB',(500,400),'white').save(p);im=w.layout(p,'#112233');self.assertEqual(im.size,(720,480));self.assertEqual(im.getpixel((360,400)),(17,34,51))
    def test_output_cannot_target_sd(self):
        with self.assertRaises(ValueError):w.new_folder('/Volumes/TEST/x')
    def test_original_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            for n in ['G3READ1.JPG','G3READ2.JPG']:(p/n).write_bytes(self.original)
            with self.assertRaises(ValueError):w.verify_original(p)
if __name__=='__main__':unittest.main()
