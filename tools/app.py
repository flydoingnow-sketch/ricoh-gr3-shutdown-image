"""Desktop package generator. No USB access or direct SD writes."""
import sys,json,threading
from pathlib import Path
import gr3_workflow as w

def smoke_test():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p=w.prepare_export(Path(td)/'probe');assert (p/'card/script/startup.ttl').is_file()
        w.audit(w.export_script())
    print('Export package and script audit passed')

def main():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    from PIL import Image,ImageTk
    root=tk.Tk();root.title('GR III 2.10 · 关机图片工具 0.1.0');root.geometry('850x790')
    frame=ttk.Frame(root,padding=18);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='选择图片，生成卡内文件',font=('',20,'bold')).pack(anchor='w')
    ttk.Label(frame,text='仅限普通 GR III · Ver.2.10。生成到电脑，手动复制到卡；相机端需开启 Script Enable。',wraplength=790).pack(anchor='w',pady=8)
    state={}
    def field(key,label,directory=True):
        row=ttk.Frame(frame);row.pack(fill='x',pady=4);ttk.Label(row,text=label,width=16).pack(side='left')
        var=tk.StringVar();state[key]=var;ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True)
        def choose():
            p=filedialog.askdirectory() if directory else filedialog.askopenfilename(filetypes=[('图片','*.png *.jpg *.jpeg *.webp *.bmp'),('所有文件','*')])
            if p:var.set(p)
        ttk.Button(row,text='选择',command=choose).pack(side='left',padx=5)
    field('original','电脑原图备份目录');field('source','自定义图片文件',False);field('candidate','候选图片目录');field('package','操作包目录');field('card','读回文件目录 / 卡')
    bg=tk.StringVar(value='#151515');reserved=tk.BooleanVar(value=True)
    row=ttk.Frame(frame);row.pack(fill='x',pady=5);ttk.Label(row,text='背景色 #RRGGBB').pack(side='left');ttk.Entry(row,textvariable=bg,width=12).pack(side='left',padx=8)
    ttk.Checkbutton(row,text='缩小上移，预留下方计数栏',variable=reserved).pack(side='left')
    status=tk.StringVar(value='首次使用：生成导出包 → 相机运行 → 备份两份 G3READ 图片到电脑。')
    ttk.Label(frame,textvariable=status,wraplength=790).pack(fill='x',pady=10)
    preview=ttk.Label(frame);preview.pack(pady=5)
    ttk.Label(frame,text='预览显示的是实际编码后的 JPEG。先检查文字、杂块与计数栏空白。',wraplength=790).pack()
    buttons=[]
    def path(key):
        text=state[key].get().strip()
        if not text:raise ValueError('请选择 '+key+' 对应路径。')
        return Path(text)
    def output():
        selected=filedialog.asksaveasfilename(title='新建电脑操作包目录（不能已存在）',initialfile='GR3-package')
        return Path(selected) if selected else None
    def show(p):
        im=Image.open(p);im.load();im.thumbnail((540,300));image=ImageTk.PhotoImage(im);preview.configure(image=image);preview.image=image
    def task(label,fn,on_success=None):
        for b in buttons:b.configure(state='disabled')
        status.set(label+'…')
        def finish(value,error=None):
            for b in buttons:b.configure(state='normal')
            if error:status.set('未完成：'+str(error));messagebox.showerror('未生成 / 校验未通过',str(error));return
            status.set(label+'完成：'+str(value))
            if on_success:on_success(value)
        def run():
            try:value=fn()
            except Exception as e:root.after(0,lambda err=e:finish(None,err))
            else:root.after(0,lambda val=value:finish(val))
        threading.Thread(target=run,daemon=True).start()
    def export():
        p=output()
        if p:task('生成原图导出包',lambda:w.prepare_export(p),lambda p:state['package'].set(str(p)))
    def check_original():
        p=path('original');task('校验原图',lambda: {'sha256':w.sha(w.verify_original(p))})
    def image():
        original=path('original');source=path('source');color=bg.get();reserve=reserved.get();p=output()
        if p:
            def done(result):state['candidate'].set(str(result));show(result/'candidate.jpg')
            task('编码候选图片（最多约45秒）',lambda:w.prepare_image(original,source,p,color,reserve),done)
    def stage(combined=False):
        original=path('original');candidate=path('candidate');p=output()
        if p:task('生成组合包' if combined else '生成临时导入包',lambda:w.prepare_candidate(original,candidate,p,combined),lambda p:state['package'].set(str(p)))
    def install():
        package=path('package');card=path('card');p=output()
        if p:task('校验读回并生成正式写入包',lambda:w.prepare_install(package,card,p),lambda p:state['package'].set(str(p)))
    def verify():
        package=path('package');card=path('card');task('校验最终读回',lambda:w.verify_install(package,card))
    def safe(fn):
        def call():
            try:fn()
            except Exception as e:messagebox.showerror('缺少信息',str(e))
        return call
    row=ttk.Frame(frame);row.pack(fill='x',pady=10)
    actions=[('1 生成原图导出包',export),('2 校验原图',check_original),('3 选择图片并编码',image),('4 生成临时导入包',stage),('5 校验并生成写入包',install),('6 校验最终读回',verify)]
    for i,(text,fn) in enumerate(actions):
        b=ttk.Button(row,text=text,command=safe(fn));b.grid(row=i//3,column=i%3,padx=4,pady=5,sticky='ew');buttons.append(b)
    for i in range(3):row.columnconfigure(i,weight=1)
    experimental=ttk.Button(frame,text='实验选项：一次开机导入并替换（跳过中间电脑哈希校验）',command=safe(lambda:stage(True)));experimental.pack(fill='x');buttons.append(experimental)
    ttk.Label(frame,text='操作结束：移走卡内 script/startup.ttl → MENU 开机关闭 Script Enable → 正常开关机确认。恢复包在操作包的 recovery/card 内，只恢复本次修改前图片。',wraplength=790).pack(pady=10)
    if "--ui-self-test" in sys.argv:
        root.after(300,lambda: (print("GUI initialized",root.winfo_width(),root.winfo_height()),root.destroy()))
    root.mainloop()

if __name__=='__main__':
    if '--self-test' in sys.argv:smoke_test()
    else:main()
