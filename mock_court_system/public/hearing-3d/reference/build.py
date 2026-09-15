import json,html,pathlib,zipfile
p=pathlib.Path(__file__).parent
roles=json.loads((p/'roles.json').read_text())
def table(head,rows):return '<table><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in head)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in r)+'</tr>' for r in rows)+'</table>'
def svg(body):return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 760"><rect width="1100" height="760" fill="#f7f6f2"/><g font-family="sans-serif" fill="#243448">'+body+'</g></svg>'
def txt(x,y,s,size=17):return f'<text x="{x}" y="{y}" font-size="{size}">{html.escape(s)}</text>'
def rect(x,y,w,h,fill='#c6ae8d'):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{fill}" stroke="#526174"/>'
coords=[('bench_center','judge',0,2.8,0,0),('clerk','clerk',-1.05,1.8,0,0),('plaintiff_counsel','plaintiff_counsel',-2.9,0.65,0,.65),('plaintiff_party','plaintiff_party',-2.9,-1.15,0,-1.15),('defendant_counsel','defendant_counsel',2.9,.65,0,.65),('defendant_party','defendant_party',2.9,-1.15,0,-1.15),('interpreter','interpreter',2.9,-2.6,0,-2.6)]
b=txt(50,48,'01 / 听证厅顶视与七席定位 · 建议尺寸 10 × 8 m',26)+rect(190,90,650,520,'#eeede8')
# scale 65; room x -5..5,z -4..4
X=lambda x:515+x*65
Z=lambda z:350-z*65
b+=rect(X(-1.5),Z(2.2),195,52)+rect(X(-2.5),Z(1.6),52,292.5)+rect(X(1.7),Z(1.6),52,292.5)+rect(X(-1.65),Z(1.35),78,39)
for i,(aid,rid,x,z,lx,lz) in enumerate(coords):
 b+=f'<circle cx="{X(x)}" cy="{Z(z)}" r="19" fill="#243448"/>'+f'<text x="{X(x)}" y="{Z(z)+6}" text-anchor="middle" fill="white" font-size="17">{i+1}</text>'
 b+=txt(870,130+i*49,f'{i+1} {roles[i][1]}',16)
b+=rect(X(4.7),Z(1),8,130,'#243448')+txt(620,635,'入口 / −Z',18)+txt(445,78,'+Z 仲裁庭方向',18)+txt(215,675,'左侧 −X：申请方；右侧 +X：被申请方；Y 向上。',18)+txt(215,709,'圆点为椅面中心；证据屏位于右墙。尺寸以锚点表为准。',17)
(p/'01_平面.svg').write_text(svg(b))
for n,typ in [(2,'正立面'),(3,'纵剖面')]:
 b=txt(50,48,f'0{n} / 听证厅{typ} · 单位 m',26)+rect(150,140,760,320,'#eeede8')
 b+=f'<path d="M150 460H910" stroke="#243448" stroke-width="4"/>'
 b+=rect(340,385,330,10)+rect(365,395,12,65)+rect(633,395,12,65)+rect(482,415,65,8,'#707b85')+rect(482,353,10,62,'#707b85')
 b+='<path d="M160 325H900" stroke="#5283a1" stroke-dasharray="8 6"/>'
 b+=txt(170,315,'视线参考 1.35（允许 1.2–1.5）',20)+txt(690,392,'桌面 0.75',20)+txt(690,427,'椅面 0.45',20)+txt(170,125,'净高建议 3.20',20)+txt(180,515,'平层布置，不设抬高法台。',21)+txt(180,552,'桌下净高建议 ≥0.68；桌面厚度建议 0.04。',20)+txt(180,592,('房间宽 10.00；横桌宽 3.00。' if n==2 else '房间深 8.00；侧桌长 4.50；前后通行空间按平面预留。'),20)+txt(180,665,'示意比例用于空间沟通；实际建模以本文尺寸和锚点为准。',18)
 (p/f'0{n}_{typ}.svg').write_text(svg(b))
states=[('supported','证据支持','#207963','✓','可表演有证据支持的事实'),('unknown','未知','#936619','?','镂空问号；不发言、不补全'),('unsupported','未支持','#a6573f','!','不作为结论依据'),('excluded','已排除','#74808d','×','灰色删除线；保留原因'),('frozen','人工冻结','#70558f','锁','保留历史外观，不自动更新')]
b=txt(45,48,'04 / 听证 HUD · 1920 × 1080 适配规范',26)+rect(45,90,1010,510,'#e5e8ea')+rect(65,110,970,56,'#243448')+'<g fill="white">'+txt(85,145,'核对通知 / 确认出庭 / 申请人陈述 / 被申请人答辩 / 举证 / 询问',19)+'</g>'+rect(775,190,240,115,'#ffffff')+txt(790,220,'当前：首席仲裁员',18)+txt(790,250,'下一发言：待确认',18)+txt(790,280,'程序状态：未知 ?',18)+rect(115,455,870,112,'#243448')+'<g fill="white">'+txt(140,485,'首席仲裁员 · Presiding Arbitrator',19)+txt(140,517,'现在核对双方收到听证通知的情况。',22)+txt(140,547,'We will now verify receipt of the hearing notice.',18)+'</g>'+txt(60,642,'字幕仅展示已确认事件文本；示例台词不能作为真实案件记录。',18)+txt(60,676,'边距 48 px；正文 28 px；英文字幕 24 px；字幕最多中英各两行。',18)+txt(60,710,'阶段条只显示当前程序节点，不暗示任何一方胜率。',18)
(p/'04_HUD.svg').write_text(svg(b))
b=txt(45,48,'05 / 溯源五态 · 颜色与形状双重编码',26)
for i,(id,zh,color,icon,desc) in enumerate(states):
 y=95+i*115;b+=rect(55,y,80,75,'#ffffff' if id=='unknown' else color)+txt(165,y+28,zh+' / '+id,23)+txt(165,y+60,icon+'  '+desc,20)
b+=txt(55,718,'未知 ≠ 未支持 ≠ 已排除；状态转换由事实与人工规则决定。',19)
(p/'05_五态色票.svg').write_text(svg(b))
sections=[]
sections.append('<h1>国际商事仲裁听证厅<br>P0 设计交付文字与图纸</h1><p>版本：2026-09-08 · 原创拟定方案 · 供法学会签与工程联调</p><div class="note">本包完成设计图文层。独立生成的人物、场景、道具与动作参考图见本次对话图片。尚不包含运行时 GLB / VRM、绑定模型或动画片段，也不代表已通过 /court3d 验收。房间尺寸、外貌年龄、配色、音色及道具尺寸均为本次建议，非原文既定值。</div>')
sections.append('<h2>1 世界观与禁用清单</h2><p>空间用于国际商事仲裁听证。以平等、专业、清晰、克制为视觉原则，通过平层桌席、商务着装和双语信息体现程序交流。深蓝为信息主色，暖灰为环境底色，木色用于桌面，金属只作局部细节。首席协调程序，双方代理陈述，企业代表参与，庭秘书记录，口译员辅助语言沟通。</p><p>禁用：法袍、国徽、正式机构徽章、法槌、抬高法台、原告／被告名牌、囚栏、法警台、律师袍架、夸张国旗墙、假发、陪审团、影视囚服及族裔刻板特征。机构标记先用中性几何占位，正式授权由法学确认。</p>')
sections.append('<h2>2 空间与锚点</h2><p>坐标系：米；X 向右，Y 向上，+Z 朝首席。房间中心为 (0,0,0)，地面 Y=0；边界 X=±5、Z=±4，建议净高 3.2。座位坐标均指椅面中心，不是人物脚底或骨骼根节点；人物根节点偏移由工程按模型校正。lookAt 是世界目标点。</p>')
sections.append(table(['锚点 ID','角色 ID','位置 (x,y,z)','lookAt','椅面高'],[(a,r,f'({x},0.45,{z})',f'({lx},1.35,{lz})','0.45') for a,r,x,z,lx,lz in coords]+[('evidence_screen','—','(4.7,1.6,0)','(0,1.6,0)','—')]))
sections.append('<p>桌面高 0.75；横桌范围 X −1.5 至 1.5、Z 1.4 至 2.2；左侧桌 X −2.5 至 −1.7，右侧桌 X 1.7 至 2.5，两侧桌 Z −2.9 至 1.6。秘书小桌 X −1.65 至 −0.45、Z 0.75 至 1.35。桌与椅按七席锚点排布，保持中心与前方通行。模型建议≤80k三角面，导出 room_hearing.glb。渲染概念若与图纸不一致，以图纸与锚点为准。</p>')
for f in ['01_平面.svg','02_正立面.svg','03_纵剖面.svg']:sections.append((p/f).read_text())
sections.append('<h2>3 七人双版本设定与名牌</h2><p>每套设定为独立3:4半身图。男女版本保持职业、配色与气质一致；具体外貌为新拟定，未声称还原此前档案。以下每个版本给出五个连续性标记，后续建模和镜头须保持。</p>')
for r in roles:
 sections.append('<h3>'+r[1]+' / '+r[0]+'</h3><p>名牌：'+r[1]+' / '+r[2]+'</p>')
 rows=[]
 for i in range(2):
  g=r[5] if not i else ('m' if r[5]=='f' else 'f');name=r[3+i];desc=r[6+i];tokens=desc.split('，')[-5:]
  while len(tokens)<5: tokens.append('商务听证')
  rows.append([name,'original' if not i else 'swap',r[0]+'_'+('original' if not i else 'swap')+'_'+g,desc,' / '.join(tokens)])
 sections.append(table(['姓名','版本','文件名前缀','外观设定','连续性五词／短语'],rows))
sections.append('<p>模型扩展名 .vrm 或 .glb。主模型与性别替换模型分别导出；骨骼使用 VRM Humanoid 或 Mixamo；统一朝向并提交一张导入检查截图。P0允许低模，P1再落实主角≤40k、配角≤15k及口型要求。图片与未绑定高面 OBJ 不能冒充运行时模型。</p>')
b=txt(45,48,'06 / 七席双语名牌 · 排版视觉稿',26)
for i,r in enumerate(roles):
 x=55+(i%2)*515;y=90+(i//2)*145
 b+=rect(x,y,480,112,'#243448')+'<g fill="white">'+txt(x+22,y+43,r[1],25)+txt(x+22,y+78,r[2],18)+'</g>'
b+=txt(55,722,'建议成品 280 × 90 mm；姓名可单列，职務名称不得替换为诉讼称谓。',17)
(p/'06_双语名牌.svg').write_text(svg(b))
sections.append((p/'06_双语名牌.svg').read_text())
sections.append('<h2>4 道具文字与尺寸建议</h2>')
sections.append(table(['ID','外观／文字','建议尺寸（米）','放置／挂点'],[
('case_file_bilingual','仲裁案卷 / ARBITRATION CASE FILE；案件编号：DEMO-001；演示材料 / DEMONSTRATION MATERIAL','0.32×0.24×0.035','桌面；左手'),('contract_en','CONTRACT；Demonstration document — not a real agreement.；Parties: Party A / Party B','0.297×0.210×0.004','桌面；左手'),('pen_silver','银色哑光细笔，无品牌','长0.14，直径0.01','右手／桌面'),('pen_dark','深灰细笔，无品牌','长0.14，直径0.01','右手／桌面'),('keyboard','低矮紧凑黑色键盘','0.36×0.13×0.025','秘书桌面'),('mic_slim','细长鹅颈话筒，开启绿灯','底座0.12×0.10；总高0.36','发言席桌面'),('earpiece_single','黑色单侧耳机，低反光','0.045×0.025×0.015','右耳'),('evidence_screen','亮：#DCE5EB；灭：#27313B','屏面1.80×1.02','右墙屏幕中心锚点')]))
sections.append('<p>道具模型交 glb 或适用的2K贴图替代；笔、话筒、耳机等立体物需保留体积。局部原点与挂点另标：笔握持点、卷宗书脊中部、耳机耳侧接触点、桌面物底面中心。速记本可在人物设定出现，独立精模列入P1。所有案件文字为演示占位，不写真实法律结论。</p>')
sections.append('<h2>5 基础动作分镜文字</h2>')
sections.append(table(['clip','时长','关键动作','适用与约束'],[('sit','3秒，可循环','0秒坐定；1.5秒轻微呼吸；3秒回到起始姿态','全员；脚掌落地，不把sit做成起立宣判'),('nod','2秒','0秒中立；0.7秒轻低头；1.4秒恢复；2秒稳定','全员；幅度克制，不表示法律认可'),('lean_forward','3秒','0秒中立；1秒髋部轻前倾；2秒停留；3秒恢复','全员；不穿桌，不滑动座椅'),('flip_file','4秒','0秒左手固定；1秒右手捏页；2秒翻页；3秒放平；4秒复位','首席／代理／秘书优先；为全员保留可重定向适配')]))
sections.append('<p>所有片段 In-place，不平移角色根节点；动作名不可改。动作图仅是姿态参考，正式片段需绑定后导出。unknown 不得新增发言或补全事实动作；P0用静止倾听占位，P1再制作 listen_only 呼吸注视循环。点头仅表达倾听，不应被系统解释为认可证据。</p>')
sections.append('<h2>6 HUD、五态与字幕</h2>')
sections.append((p/'04_HUD.svg').read_text()+(p/'05_五态色票.svg').read_text())
sections.append(table(['中文','英文'],[('核对通知','Verify Notice'),('确认出庭','Confirm Attendance'),('申请人陈述','Claimant’s Statement'),('被申请人答辩','Respondent’s Response'),('举证','Presentation of Evidence'),('询问','Questions'),('当前发言','Current Speaker'),('下一发言','Next Speaker'),('待确认','To Be Confirmed'),('暂无可核验信息','No Verifiable Information Available')]))
sections.append(table(['状态ID','中文','色值','图形及行为'],[(a,b,c,d+'；'+e) for a,b,c,d,e in states]))
sections.append('<p>UI建议画布1920×1080，安全边距48，主色#243448，背景#F7F6F2；中文使用系统无衬线字体。顶部程序条高80；底部字幕容器按行数自适应，建议高180，中英文各最多两行。中文正文28px，英文24px，名牌主职务28px、英文20px。当前阶段使用下划线与色块双重标识。屏幕缩小时允许阶段条横向滚动，字幕不能遮挡关键发言人物面部。不得出现原告胜率、法庭调查、宣判。图中字幕仅为演示用语，实际字幕由确认事件驱动。</p>')
sections.append('<h2>7 镜头与音色提示</h2><p>wide建议机位 (0,1.35,−3.7)，lookAt (0,1.35,1.0)，水平视场角约90°作为起点，联调时以七席不裁切、墙体不遮挡为准。全景图是氛围参考而非精确相机输出。特写、过肩和双人镜头属于P1。</p>')
sections.append(table(['角色','original / swap','语种与表达提示'],[(r[1],('女 / 男' if r[5]=='f' else '男 / 女'),('英语为主，清晰自然，可选中文' if r[0]=='defendant_party' else '中英双语切换，节奏均匀，转述中性' if r[0]=='interpreter' else '普通话为主，英文可切换；清晰、克制、自然')) for r in roles]))
sections.append('<p>首席：沉稳、适中停顿；秘书：简洁、准确；双方代理：论述清楚，避免表演性对抗；企业代表：自然正式；口译：中性、忠实。音色是选声提示，不要求模仿真实人物；具体TTS与语音队列由计算机接入。</p>')
sections.append('<h2>8 文件组织与验收文字</h2><p>文件夹：00_总则、01_场景A_听证厅、04_角色、05_道具、06_动画、07_UI规范、08_概念图、09_验收。当前图纸SVG可编辑，人物图为栅格设定；后续补交Blender/C4D等源文件、贴图、骨骼与模型。</p>')
sections.append(table(['检查项','通过标准','当前状态'],[('世界观、名牌与规范','仲裁语义，无禁用元素','本包已给出，待法学会签'),('空间图纸及锚点','7席+证据屏；单位米','本包建议方案，待工程对齐'),('14套人物图','original / swap 独立半身设定','见本次生成图片'),('room_hearing.glb','可打开，朝向正确，≤80k','待建模与导出'),('角色模型','按文件名导入并正确入座','待建模、绑定与导出'),('基础动画','四种clip可播放、不穿模','已给分镜文字；动画待制作'),('道具','可用低模与挂点','已给图文；模型待制作'),('HUD与镜头','职称、字幕、发言角色对应','已给规范；待接入'),('/court3d回放','能完整播放一次听证','待工程联调验收')]))
sections.append('<div class="note">交接说明：请先按本包锚点确认座位和模型朝向，再逐项替换房间、人物和道具。任何尚未核实的案件事实保持未知，不以补画人物发言或动画推定事实。设计负责视觉资产与规范；工程负责代码、TTS、字幕队列、状态机和接入；法学负责术语与程序语义会签。</div>')
css='body{font-family:system-ui,sans-serif;color:#243448;background:#eee;margin:0;line-height:1.7}main{max-width:1150px;margin:30px auto;padding:60px;background:white}h1{font-size:38px}h2{margin-top:50px;border-bottom:2px solid #c6ae8d;padding-bottom:12px}table{border-collapse:collapse;width:100%;font-size:14px;margin:20px 0}td,th{border:1px solid #d9dee2;padding:10px;text-align:left;overflow-wrap:anywhere}th{background:#eaf0f3}.note{background:#f3f0e8;padding:22px}svg{width:100%;margin:20px 0;border:1px solid #ddd} @media print{body{background:white}main{margin:0;padding:0}h2{break-after:avoid}tr,svg{break-inside:avoid}}'
(p/'P0_设计交付说明.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>P0设计交付说明</title><style>'+css+'</style><main>'+''.join(sections)+'</main></html>')
with zipfile.ZipFile(p.parent/'P0_图纸与文字交付包.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in p.iterdir():
  if f.suffix in ['.svg','.html','.json','.py']:z.write(f,f.name)
print('Created HTML, 5 SVG diagrams, source data and ZIP')
