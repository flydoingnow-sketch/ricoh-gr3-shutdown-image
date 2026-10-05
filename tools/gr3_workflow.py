"""GR III 2.10 host-side packages. Derived TTL builder: tools/vendor/NOTICE.
No camera/USB access; outputs local folders only. See docs/VALIDATION.md.
"""
from pathlib import Path
from io import BytesIO
import hashlib,json,secrets,sys,re,time,random
from PIL import Image,ImageOps,ImageDraw
from jpeg_profile import validate_original,validate_candidate,parse_jpeg
sys.path.insert(0,str(Path(__file__).resolve().parent / "vendor"))
from vendor import gr3x_urban_shutdown as ttl

TARGET=r'B:\Resource\Jpeg\GoodBye.jpg'
SIZE=7264
ORIGINAL_SHA='dff9ba0ad2c7ea2697b19470cf6c695337651ee0ef415a6d3359a7f318ff3c79'
ENTRY={'00078350.588':b'[OPEN_FACTORY_DEBUG_MENU]\r\n','DEVELOP.MOD':bytes.fromhex('07012c1f10031e16052d')}

def sha(data):return hashlib.sha256(data).hexdigest()

def new_folder(folder):
    folder=Path(folder).resolve()
    # A local preparation tool, never write directly to removable volumes.
    if str(folder).startswith('/Volumes/') or (sys.platform=='win32' and folder.drive!=Path.home().drive):
        raise ValueError('请先生成到电脑本地文件夹，再手动复制到卡上。')
    folder.mkdir(parents=True,exist_ok=False)
    return folder

def card_files(folder,script,logs=()):
    card=folder/'card';(card/'script').mkdir(parents=True)
    for name,data in ENTRY.items():(card/name).write_bytes(data)
    (card/'script/startup.ttl').write_bytes(script)
    for name in logs:(card/name).write_bytes(b'')
    return card

def load_manifest(folder):
    m=json.loads((Path(folder)/'manifest.json').read_text(encoding='utf-8'))
    if m.get('model')!='GR III' or m.get('firmware')!='2.10':raise ValueError('操作包型号/版本不匹配。')
    if 'names' in m and m['names']!=names(m['token']):raise ValueError('操作包资源路径被修改。')
    return m

def save_manifest(folder,m):
    (folder/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')

def export_script():
    lines=[f"filestat '{TARGET}' n",'if result <> 0 then','exit','endif',f'if n <> {SIZE} then','exit','endif']
    for n in ('G3READ1.JPG','G3READ2.JPG'):
        lines += [f"getfileattr 'C:\\{n}'",'if result <> -1 then','exit','endif']
    for n in ('G3READ1.JPG','G3READ2.JPG'):
        lines += [f"filecopy '{TARGET}' 'C:\\{n}'",f"filestat 'C:\\{n}' n",'if result <> 0 then','exit','endif',f'if n <> {SIZE} then','exit','endif']
    return ('\r\n'.join(lines)+ '\r\nexit\r\n').encode('ascii')

def prepare_export(output):
    p=new_folder(output);script=export_script();card_files(p,script)
    save_manifest(p,{'kind':'export','model':'GR III','firmware':'2.10','script_sha256':sha(script),'internal_write_enabled':False})
    (p/'操作说明.txt').write_text('将 card 内全部内容复制到卡根目录。MENU+开机进入工厂菜单，只开启 Script Enable，然后关机。正常开机运行一次，等读写停止后关机。把 G3READ1.JPG、G3READ2.JPG 复制到电脑，用工具校验。移走 script/startup.ttl，再进工厂菜单关闭 Script Enable。首次必须是未修改的普通 GR III 2.10 原图；不同哈希停止。',encoding='utf-8')
    return p

def verify_original(folder):
    p=Path(folder);a=(p/'G3READ1.JPG').read_bytes();b=(p/'G3READ2.JPG').read_bytes()
    validate_original(a)
    if a!=b:raise ValueError('两份原图不一致，停止。')
    im=Image.open(BytesIO(a));im.load()
    return a

def layout(source,background='#151515',reserved=True):
    im=ImageOps.exif_transpose(Image.open(source)).convert('RGBA')
    if im.width*im.height>50_000_000:raise ValueError('图片过大，请先缩小。')
    # 720x480 target, optional 40% lower area reserved for camera overlay.
    canvas=Image.new('RGB',(720,480),background)
    box=(430,245) if reserved else (720,480)
    fitted=ImageOps.contain(im,box,Image.Resampling.LANCZOS)
    x=(720-fitted.width)//2;y=(285-fitted.height)//2 if reserved else (480-fitted.height)//2
    canvas.paste(fitted,(x,max(0,y)),fitted)
    return canvas

def encode(original,image,timeout=45,max_trials=6000):
    """Bounded exact-size encoder. DC is preserved during table search.
    Some artwork cannot fit; no padding, truncation or low-quality forcing.
    """
    validate_original(original)
    jfif=next(p['raw'] for p in parse_jpeg(original) if p['marker']=='E0')
    start=time.monotonic();attempts=0
    def encoded(t=None,q=75):
        nonlocal attempts
        b=BytesIO();options={'qtables':t} if t is not None else {'quality':q}
        image.save(b,format='JPEG',subsampling=2,optimize=True,progressive=False,**options)
        parts=parse_jpeg(b.getvalue());attempts+=1
        return parts[0]['raw']+jfif+b''.join(p['raw'] for p in parts[1:] if p['marker']!='E0')
    # Balanced chroma/luma: no extremely coarse chroma and no DC randomization.
    samples=[(q,encoded(q=q)) for q in range(25,96)]
    nearest=min(samples,key=lambda x:abs(len(x[1])-SIZE))
    if not any(len(b)>=SIZE for q,b in samples) or not any(len(b)<=SIZE for q,b in samples):
        raise ValueError('图片无法在当前质量范围内达到 7264 字节；请减少纹理、缩小标志或换纯色背景。')
    exact=next((b for q,b in samples if len(b)==SIZE),None)
    base={k:list(v) for k,v in Image.open(BytesIO(nearest[1])).quantization.items()}
    error=abs(len(nearest[1])-SIZE);rng=random.Random(20261005)
    while exact is None and attempts<max_trials and time.monotonic()-start<timeout:
        t={k:[v if i==0 else max(1,min(255,v+rng.choice([-2,-1,0,0,0,1,2]))) for i,v in enumerate(vs)] for k,vs in base.items()}
        b=encoded(t);e=abs(len(b)-SIZE)
        if e==0:exact=b;break
        if e<error:base,error=t,e
        elif attempts%300==0:
            base={k:list(v) for k,v in Image.open(BytesIO(nearest[1])).quantization.items()};error=abs(len(nearest[1])-SIZE)
    if exact is None:raise ValueError('有界编码搜索未找到等长图片；没有生成写入包。请简化图片后重试。')
    validate_candidate(original,exact);im=Image.open(BytesIO(exact));im.load()
    return exact,{'trials':attempts,'desktop_decode_verified':True,'camera_display_verified':False}

def token_valid(token):
    if not re.fullmatch('[A-F0-9]{4}',token):raise ValueError('Invalid package token')
    return token

def names(token):
    token_valid(token)
    return {'backup':rf'B:\Resource\Jpeg\R{token}OL.JPG','temporary':rf'B:\Resource\Jpeg\R{token}NW.JPG','log1':f'R{token}A.TXT','log2':f'R{token}B.TXT',
            'before':f'R{token}P.JPG','backup_read':f'R{token}O.JPG','candidate_read':f'R{token}N.JPG','final':f'R{token}F.JPG','rollback':f'R{token}R.JPG'}

def stage_script(candidate,n):
    ttl.SIZE=SIZE;s=ttl.Script('C:\\'+n['log1']);s.size(TARGET,101)
    s.add(f"getfileattr '{TARGET}'",'targetattr = result');s.guard('targetattr <> 32',103)
    for i,p in enumerate([n['backup'],n['temporary']]+['C:\\'+n[k] for k in ['before','backup_read','candidate_read']]):
        s.add(f"getfileattr '{p}'");s.guard('result <> -1',110+i)
    s.copy(TARGET,n['backup']);s.size(n['backup'],120)
    for k,src in [('before',TARGET),('backup_read',n['backup'])]:s.copy(src,'C:\\'+n[k]);s.size('C:\\'+n[k],130)
    s.checkpoint('backup_saved')
    s.add(f"filecreate image '{n['temporary']}'");s.guard('image < 0',201)
    s.add('fileclose image',f"filetruncate '{n['temporary']}' {SIZE}");s.size(n['temporary'],202)
    s.add(f"fileopen image '{n['temporary']}' 0");s.guard('image < 0',204)
    index=0
    while index<len(candidate):
        if candidate[index]==0:index+=1;continue
        begin=index
        while index<len(candidate) and candidate[index]!=0 and index-begin<42:index+=1
        s.add(f'fileseek image {begin} 0','filewrite image '+''.join(f'#{v}' for v in candidate[begin:index]))
    s.add('fileclose image');s.size(n['temporary'],205)
    s.copy(n['temporary'],'C:\\'+n['candidate_read']);s.size('C:\\'+n['candidate_read'],207)
    s.checkpoint('candidate_saved');data=s.finish();audit(data,candidate)
    return data

def install_script(n):
    ttl.SIZE=SIZE;s=ttl.Script('C:\\'+n['log2'])
    for i,p in enumerate([TARGET,n['backup'],n['temporary']]):s.size(p,101+2*i)
    s.add(f"getfileattr '{TARGET}'",'targetattr = result');s.guard('targetattr <> 32',107)
    for i,k in enumerate(['final','rollback']):
        s.add(f"getfileattr 'C:\\{n[k]}'");s.guard('result <> -1',110+i)
    s.checkpoint('write_started');s.add('attempted = 1');s.copy(n['temporary'],TARGET)
    s.size(TARGET,201,'rollback');s.copy(TARGET,'C:\\'+n['final']);s.size('C:\\'+n['final'],203,'rollback')
    s.add(f"getfileattr '{TARGET}'");s.guard('result <> targetattr',205,'rollback')
    s.checkpoint('installed_readback_saved');s.add('goto done',':rollback','restored = 1')
    s.copy(n['backup'],TARGET);s.size(TARGET,210);s.copy(TARGET,'C:\\'+n['rollback']);s.size('C:\\'+n['rollback'],212)
    s.checkpoint('rollback_saved');data=s.finish();audit(data)
    return data

def restore_script(n,token):
    ttl.SIZE=SIZE;log=f'S{token}.TXT';s=ttl.Script('C:\\'+log)
    for p in [TARGET,n['backup']]:s.size(p,101)
    s.add(f"getfileattr '{TARGET}'");s.guard('result <> 32',105)
    output=f'S{token}.JPG';s.add(f"getfileattr 'C:\\{output}'");s.guard('result <> -1',107)
    s.add('attempted = 1');s.copy(n['backup'],TARGET);s.size(TARGET,201)
    s.copy(TARGET,'C:\\'+output);s.size('C:\\'+output,203);s.add('restored = 1')
    data=s.finish();audit(data);return data,log,output

def audit(script,candidate=None):
    lines=script.decode('ascii').splitlines()
    if max(map(len,lines))>=256:raise ValueError('Line limit')
    if sum(x.startswith('if ') for x in lines)!=lines.count('endif'):raise ValueError('Conditional mismatch')
    labels={x[1:]:i for i,x in enumerate(lines) if x.startswith(':')}
    if len(labels)!=sum(x.startswith(':') for x in lines):raise ValueError('Duplicate labels')
    for i,x in enumerate(lines):
        if x.startswith('goto ') and labels[x[5:]]<=i:raise ValueError('Backward jump')
        if x.startswith(('filedelete ','setfileattr ')):raise ValueError('Forbidden operation')
    if candidate is not None:
        data=bytearray(SIZE);pos=None
        for x in lines:
            if x.startswith('fileseek image '):pos=int(x.split()[2])
            elif x.startswith('filewrite image '):
                b=bytes(map(int,re.findall('#(\\d+)',x)))
                if pos is None or pos+len(b)>SIZE:raise ValueError('Payload bounds')
                data[pos:pos+len(b)]=b
        if bytes(data)!=candidate:raise ValueError('Embedded JPEG mismatch')

def prepare_image(original_folder,source,output,background='#151515',reserved=True):
    original=verify_original(original_folder);image=layout(source,background,reserved)
    candidate,details=encode(original,image)
    p=new_folder(output);image.save(p/'artwork.png');(p/'candidate.jpg').write_bytes(candidate)
    save_manifest(p,{'kind':'candidate','model':'GR III','firmware':'2.10','original_sha256':sha(original),'candidate_sha256':sha(candidate),**details})
    return p

def prepare_candidate(original_folder,candidate_folder,output,combined=False):
    original=verify_original(original_folder);cp=Path(candidate_folder);candidate=(cp/'candidate.jpg').read_bytes()
    validate_candidate(original,candidate)
    token=secrets.token_hex(2).upper();n=names(token);a=stage_script(candidate,n);b=install_script(n)
    if combined:
        a=a.replace(b'goto done',b'goto stage_done').replace(b':done',b':stage_done')
        if not a.endswith(b'exit\r\n'):raise ValueError('Unexpected termination')
        script=a[:-6]+b'if error <> 0 then\r\nexit\r\nendif\r\n'+b
        audit(script,candidate)
    else:script=a
    p=new_folder(output);card_files(p,script,[n['log1'],n['log2']] if combined else [n['log1']])
    m={'kind':'combined' if combined else 'stage','model':'GR III','firmware':'2.10','token':token,'names':n,'candidate_sha256':sha(candidate),'original_sha256':sha(original),'script_sha256':sha(script),'hardware_wrapper_verified':False}
    (p/'candidate.jpg').write_bytes(candidate);save_manifest(p,m)
    recovery=p/'recovery';recovery.mkdir();r,log,jpg=restore_script(n,token);card_files(recovery,r,[log]);save_manifest(recovery,{'kind':'restore','model':'GR III','firmware':'2.10','token':token,'names':n,'log':log,'readback':jpg,'parent_token':token})
    (p/'操作说明.txt').write_text('将 card 内文件复制到卡根目录，只开启 Script Enable 后正常开机执行一次。等读写停止后关机，按 manifest 中的名称检查日志与图片。分步版先用工具校验 stage 读回，再生成 install；组合版直接写入，须最终读回校验。不要清空日志重跑。recovery 是恢复本次修改前图片的独立操作包，不要一起复制。结束后移走 script/startup.ttl，再进入工厂菜单关闭 Script Enable。详见项目安装教程。',encoding='utf-8')
    return p

def read_log(path):
    lines=Path(path).read_text(encoding='ascii').splitlines()
    if not lines or len(lines)%2:raise ValueError('日志缺失或不完整。')
    pairs=list(zip(lines[::2],lines[1::2]))
    if len(set(k for k,v in pairs))!=len(pairs):raise ValueError('日志重复，停止。')
    return dict(pairs)

def check_log(path,required):
    log=read_log(path)
    for k,v in required.items():
        if log.get(k)!=v:raise ValueError('日志未通过：'+k)
    return log

def verify_stage(package,card):
    p=Path(package);c=Path(card);m=load_manifest(p);n=m['names']
    log=check_log(c/n['log1'],{'started':'1','backup_saved':'1','candidate_saved':'1','error':'0','attempted':'0','restored':'0','completed':'1'})
    before=(c/n['before']).read_bytes();backup=(c/n['backup_read']).read_bytes();new=(c/n['candidate_read']).read_bytes()
    if len(before)!=SIZE or before!=backup:raise ValueError('当前图片备份不一致。')
    if sha(new)!=m['candidate_sha256']:raise ValueError('新图片完整哈希不匹配。')
    for d in [before,backup,new]:im=Image.open(BytesIO(d));im.load()
    return {'previous_sha256':sha(before),'candidate_sha256':sha(new),'log':log}

def prepare_install(package,card,output):
    p=Path(package);v=verify_stage(p,card);m=load_manifest(p);script=install_script(m['names'])
    out=new_folder(output);card_files(out,script,[m['names']['log2']]);m.update(kind='install',stage_verified=True,previous_sha256=v['previous_sha256'],script_sha256=sha(script));save_manifest(out,m)
    return out

def verify_install(package,card):
    p=Path(package);c=Path(card);m=load_manifest(p);n=m['names']
    check_log(c/n['log2'],{'started':'1','write_started':'1','installed_readback_saved':'1','error':'0','attempted':'1','restored':'0','completed':'1'})
    data=(c/n['final']).read_bytes()
    if len(data)!=SIZE or sha(data)!=m['candidate_sha256']:raise ValueError('最终读回哈希不匹配。')
    im=Image.open(BytesIO(data));im.load()
    return {'full_readback_verified':True,'camera_display_confirmation_required':True}
