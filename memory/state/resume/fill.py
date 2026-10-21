import json,re
c=json.load(open(__import__('sys').argv[1]))['content']
t=open('/home/user/work/.claude/skills/kami/assets/templates/resume.html',encoding='utf-8').read()
head=t[:t.index('</head>')+len('</head>')+1]
head=head.replace('{{姓名}} · 简历','黄振远 · 简历').replace('content="{{姓名}}"','content="黄振远"').replace('{{摘要}}','连锁餐饮与文旅集团运营高管，覆盖门店运营、集团供应链与品牌运营的 19 年经验').replace('{{关键词}}','连锁餐饮,运营管理,供应链,集团采购,品牌运营')
def hl(t,keys):
    for k in keys: t=t.replace(k,f'<span class="hl">{k}</span>',1)
    return t
def unit(v):
    m=re.match(r'^([+\d\.,]+)\s*(.*)$',v); return (m.group(1),m.group(2)) if m else (v,'')
metrics=''.join(f'  <div class="metric"><span class="metric-value serif">{unit(m["value"])[0]}<span class="unit">{unit(m["value"])[1]}</span></span><span class="metric-label">{m["label"]}</span></div>\n' for m in c['metrics'])
heads=["门店到大区","集团供应链","品牌运营"]
tl=''.join(f'    <div class="tl-step">\n      <div class="tl-top"><div class="tl-year serif">{x["period"]}</div><div class="tl-head">{heads[i]}</div></div>\n      <div class="tl-body">{x["milestone"]}</div>\n    </div>\n' for i,x in enumerate(c['timeline']))
kinds=['港股上市（6831.HK）','华南头部文旅集团','港股上市（6862.HK）','PE / VC 条线']
roles=['品牌运营总经理','供应链管理部总经理','华南大区运营官','项目顾问']
hls=[['13 个百分点','25%'],['34%','3.4 亿余元'],['133 家','22%'],['20%']]
def proj(i,p):
    return f'''  <div class="project">
    <div class="proj-head">
      <span class="proj-name serif">{p["name"]}</span>
      <span class="proj-kind">· {kinds[i]} · {p["period"]}</span>
      <span class="proj-role">{roles[i]}</span>
    </div>
    <div class="proj-lines">
      <div class="proj-row"><div class="proj-label">角色</div><div class="proj-text">{p["role"]}</div></div>
      <div class="proj-row"><div class="proj-label">动作</div><div class="proj-text">{"".join(p["actions"])}</div></div>
      <div class="proj-row"><div class="proj-label">结果</div><div class="proj-text">{hl(p["impact"],hls[i])}</div></div>
    </div>
  </div>
'''
P=c['projects']
labels=['扩张<br>与选址','供应链<br>与集采','数字化<br>运营','组织<br>与人才','资本<br>视角']
emph=['133 家','34%','SAP SRM','78%','PE/VC']
SPAN='<span class="em-brand">{}</span>'
skills=''
for l,sk,em in zip(labels,c['skills'],emph):
    skills+='  <div class="skill-row">\n    <div class="skill-label">'+l+'</div>\n    <div class="skill-body">'+sk.replace(em,SPAN.format(em),1)+'</div>\n  </div>\n'

e=c['education'][0]
body=f'''<body>

<div class="header">
  <div>
    <div class="name serif">{c["name"]}<span class="alias">HUANG ZHENYUAN</span></div>
  </div>
  <div class="contact">
    <span class="role">{c["title"]}</span>
    <br>
    {c["contact"]}
  </div>
</div>

<div class="metrics">
{metrics}</div>

<section>
  <div class="section-title">个人简介</div>
  <div class="summary">{c["summary"]}</div>
</section>

<section>
  <div class="section-title">工作经历<span class="sub">2007 – 至今 · 投行 → 门店运营 → 集团供应链 → 品牌运营</span></div>
  <div class="timeline">
{tl}  </div>
{proj(0,P[0])}{proj(1,P[1])}</section>

<section class="page-break">
{proj(2,P[2])}{proj(3,P[3])}</section>

<section>
  <div class="section-title">核心能力</div>
{skills}</section>

<section class="no-break">
  <div class="section-title">教育背景</div>
  <div class="edu-row">
    <div><span class="school serif">{e["school"]}</span><span class="major">　· {e["degree"]}</span></div>
    <div class="date">{e["period"]}</div>
  </div>
</section>

<section class="no-break">
  <div class="section-title">荣誉</div>
  <div class="edu-row"><div><span class="school serif">海底捞</span><span class="major">　· 区域最佳运营官（连续 3 年）· 创新流程奖</span></div><div class="date"></div></div>
  <div class="edu-row"><div><span class="school serif">绿茶集团</span><span class="major">　· 年度卓越管理奖</span></div><div class="date"></div></div>
</section>

</body>
</html>
'''
open('resume.html','w',encoding='utf-8').write(head+body)
