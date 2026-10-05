#!/usr/bin/env python3
"""Publish this source-only repository with a locally supplied GitHub token.
Does not print/store credentials. Requires an existing local commit.
"""
import argparse,base64,getpass,json,os,re,ssl,subprocess,sys,urllib.request,urllib.error
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--name',default='ricoh-gr3-shutdown-image');x=p.parse_args()
if not re.fullmatch('[A-Za-z0-9_.-]{1,100}',x.name):p.error('Invalid repository name')
root=Path(__file__).resolve().parent
for args in [['git','rev-parse','--verify','HEAD'],['git','diff','--exit-code'],['git','diff','--cached','--exit-code']]:
 if subprocess.run(args,cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:p.exit(1,'请先完成本地提交，保持源码目录干净。\n')
token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN') or getpass.getpass('GitHub token（只在本机隐藏输入，不上传到聊天）: ')
if not token:p.exit(1,'没有 GitHub 凭据，未发布。\n')
context=ssl.create_default_context()
# Respect a locally supplied CA file without disabling TLS verification.
if os.environ.get('SSL_CERT_FILE'):context.load_verify_locations(os.environ['SSL_CERT_FILE'])
def api(path,body=None):
 req=urllib.request.Request('https://api.github.com'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json','User-Agent':'GR3ImageTool-publisher'})
 with urllib.request.urlopen(req,context=context,timeout=30) as r:return json.load(r)
try:
 owner=api('/user')['login']
 try:
  existing=api('/repos/'+owner+'/'+x.name)
 except urllib.error.HTTPError as e:
  if e.code!=404:raise
  repo=api('/user/repos',{'name':x.name,'description':'GR III 2.10 shutdown-image research and desktop package generator; noncommercial source license','private':False,'auto_init':False})
 else:p.exit(1,'该账号已存在同名仓库，未覆盖：'+existing['html_url']+'\n')
 url=repo['clone_url']
 if subprocess.run(['git','remote','get-url','origin'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
  p.exit(1,'已创建空仓库 '+repo['html_url']+'；本地已有 origin，未覆盖。请核对后手动推送。\n')
 subprocess.run(['git','remote','add','origin',url],cwd=root,check=True)
 env=os.environ.copy();env['GIT_TERMINAL_PROMPT']='0';env['GIT_CONFIG_COUNT']='1';env['GIT_CONFIG_KEY_0']='http.https://github.com/.extraheader'
 env['GIT_CONFIG_VALUE_0']='AUTHORIZATION: basic '+base64.b64encode(('x-access-token:'+token).encode()).decode()
 subprocess.run(['git','push','-u','origin','HEAD:main'],cwd=root,env=env,check=True)
 print('已发布：'+repo['html_url'])
except urllib.error.HTTPError as e:p.exit(1,'GitHub API 请求失败，HTTP '+str(e.code)+'；未声明发布成功。\n')
except (OSError,subprocess.CalledProcessError) as e:p.exit(1,'发布未完成：'+type(e).__name__+'；若已创建仓库，请保留并手动继续推送。\n')
