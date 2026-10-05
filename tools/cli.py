import argparse,json
from pathlib import Path
import gr3_workflow as w
p=argparse.ArgumentParser(description='GR III 2.10 关机图片工具，只生成本地文件')
s=p.add_subparsers(dest='command',required=True)
def arg(sub,*names):
 for n in names:sub.add_argument(n,type=Path)
a=s.add_parser('export');arg(a,'output')
a=s.add_parser('check-original');arg(a,'folder')
a=s.add_parser('encode');arg(a,'original_folder','image','output');a.add_argument('--background',default='#151515');a.add_argument('--full-frame',action='store_true')
a=s.add_parser('stage');arg(a,'original_folder','candidate_folder','output');a.add_argument('--combined',action='store_true')
a=s.add_parser('install');arg(a,'package','readbacks','output')
a=s.add_parser('verify');arg(a,'package','readbacks')
x=p.parse_args()
try:
 if x.command=='export':result=w.prepare_export(x.output)
 elif x.command=='check-original':result={'sha256':w.sha(w.verify_original(x.folder))}
 elif x.command=='encode':result=w.prepare_image(x.original_folder,x.image,x.output,x.background,not x.full_frame)
 elif x.command=='stage':result=w.prepare_candidate(x.original_folder,x.candidate_folder,x.output,x.combined)
 elif x.command=='install':result=w.prepare_install(x.package,x.readbacks,x.output)
 else:result=w.verify_install(x.package,x.readbacks)
 print(json.dumps(result,ensure_ascii=False,indent=2) if isinstance(result,dict) else str(result))
except (ValueError,OSError) as e:p.exit(1,'未完成：'+str(e)+'\n')
