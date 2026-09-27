"""稻城亚丁 · 配乐合成（全部程序生成，无采样、无版权素材）
藏式氛围：D 持续低音 + 颂钵 + D 小调五声音阶笛声 + 法铃（tingsha）+ 风声 + 远处手鼓。
与画面对点：0s/12s/36s 颂钵；19/25/31s 法铃（换场）；6.5s 日照金山时笛声进入；31–36s 经幡场加风与鼓。
用法：python3 music.py out/music.wav
"""
import sys, wave, numpy as np
SR=44100; T=40.0; N=int(SR*T); t=np.arange(N)/SR
rng=np.random.default_rng(20260927)
L=np.zeros(N); R=np.zeros(N)
def add(sig,t0,pan=0.5,gain=1.0):
    i=int(t0*SR); n=min(len(sig),N-i)
    if n<=0: return
    L[i:i+n]+=sig[:n]*gain*np.cos(pan*np.pi/2); R[i:i+n]+=sig[:n]*gain*np.sin(pan*np.pi/2)
def note(f): return 293.6648*2**((f)/12)   # 以 D4 为 0 的半音

# ---------- 持续低音（D2 + A2 + D3，左右声道微失谐，缓慢呼吸） ----------
def drone():
    env=np.clip(t/5,0,1)*np.clip((T-t)/3.0,0,1)
    breath=0.75+0.25*np.sin(2*np.pi*0.045*t)
    swell=1+0.9*np.clip((t-7.0)/2.0,0,1)*np.clip((13.0-t)/1.5,0,1)   # 日照金山（7–12s）渐强
    out=[]
    for det in (-0.12,0.12):
        s=(1.0*np.sin(2*np.pi*(73.42+det)*t)+0.55*np.sin(2*np.pi*(110.0+det*1.3)*t+1.1)
           +0.35*np.sin(2*np.pi*(146.83-det)*t+2.0)+0.10*np.sin(2*np.pi*(220.0+det)*t+0.4))
        out.append(s*env*breath*swell)
    return out
dl,dr=drone(); L+=dl*0.16; R+=dr*0.16

# ---------- 颂钵：非谐和分音 + 成对微失谐产生拍频，长衰减 ----------
def bowl(f0,dur=11.0):
    n=int(dur*SR); tt=np.arange(n)/SR; s=np.zeros(n)
    for ratio,amp,dec,beat in [(1,1.0,9.0,0.9),(2.76,0.55,5.5,1.7),(5.40,0.28,3.2,2.6),(8.93,0.12,1.8,3.9)]:
        f=f0*ratio
        s+=amp*np.exp(-tt/dec)*(np.sin(2*np.pi*f*tt)+np.sin(2*np.pi*(f+beat)*tt+0.7))*0.5
    s*=np.clip(tt/0.006,0,1)
    return s
for t0,f0,g in [(0.15,146.83,0.55),(12.0,146.83,0.42),(36.0,146.83,0.6)]:
    add(bowl(f0),t0,0.5,g)

# ---------- 法铃：高频金属音，两枚相碰略错开 ----------
def tingsha(f0=2230.0,dur=3.5):
    n=int(dur*SR); tt=np.arange(n)/SR; s=np.zeros(n)
    for ratio,amp,dec in [(1,1.0,2.4),(2.32,0.45,1.2),(3.91,0.2,0.6)]:
        s+=amp*np.exp(-tt/dec)*np.sin(2*np.pi*f0*ratio*tt)
    return s*np.clip(tt/0.002,0,1)
for t0 in (19.0,25.0,31.0):
    add(tingsha(2230.0),t0,0.35,0.10); add(tingsha(2262.0),t0+0.045,0.65,0.09)

# ---------- 笛声：正弦 + 少量谐波，气息噪声，颤音，起音滑入 ----------
noise_bank=rng.standard_normal(N)
def flute(semi,dur):
    n=int(dur*SR); tt=np.arange(n)/SR; f=note(semi)
    bend=2**((-0.35*np.exp(-tt/0.06))/12)                          # 起音从低约 35 音分滑入
    vib=1+0.0045*np.sin(2*np.pi*5.2*tt)*np.clip((tt-0.35)/0.4,0,1)  # 0.35s 后逐渐加颤音
    ph=2*np.pi*np.cumsum(f*bend*vib)/SR
    tone=np.sin(ph)+0.22*np.sin(2*ph)+0.07*np.sin(3*ph)
    env=np.clip(tt/0.12,0,1)*np.clip((dur-tt)/0.35,0,1)
    br=noise_bank[:n]*0.10*np.exp(-tt/0.18)                         # 起音气息
    return (tone*env+br*np.clip(tt/0.02,0,1))*0.9
# 乐句（音名以 D4=0：D0 F3 G5 A7 C10 D12）
D,F,G,A,C,D5=0,3,5,7,10,12
PHRASES=[(6.6,[(A,1.2),(G,0.6),(A,0.8),(D5,1.6),(C,0.7),(A,1.6)]),          # 日照金山
         (13.0,[(D,1.0),(F,0.6),(G,1.0),(A,1.8),(G,0.6),(F,0.6),(D,1.4)]),    # 三神山
         (19.6,[(A,1.0),(C,0.8),(D5,2.0),(C,0.6),(A,0.8),(G,1.2)]),           # 牛奶海
         (25.6,[(G,0.8),(A,0.8),(C,1.2),(A,0.6),(G,0.6),(F,0.8),(G,1.6)]),    # 彩林
         (31.6,[(D5,1.2),(C,0.6),(A,1.0),(G,0.6),(A,1.6)]),                   # 红草地
         (36.6,[(D,3.2)])]                                                    # 结尾长音
for start,notes in PHRASES:
    tc=start
    for semi,dur in notes:
        add(flute(semi,dur+0.25),tc,0.42,0.19 if start<12 else 0.16); tc+=dur

# ---------- 风声：带通噪声（FFT 频域整形），缓慢起伏；经幡场加强 ----------
def band_noise(lo,hi,seed):
    x=np.random.default_rng(seed).standard_normal(N); X=np.fft.rfft(x); fr=np.fft.rfftfreq(N,1/SR)
    X*=np.exp(-0.5*((np.log(fr+1)-np.log((lo*hi)**0.5))/0.55)**2); return np.fft.irfft(X,N)
wl,wr=band_noise(250,1800,1),band_noise(250,1800,2)
wenv=(0.25+0.2*np.sin(2*np.pi*0.11*t+1.0)+0.15*np.sin(2*np.pi*0.037*t))
wenv*=1+1.6*np.clip((t-30.6)/0.8,0,1)*np.clip((36.2-t)/0.8,0,1)   # 31–36s 经幡场风更大
wenv*=np.clip(t/3,0,1)*np.clip((T-t)/2.5,0,1)
wl/=np.abs(wl).max(); wr/=np.abs(wr).max(); L+=wl*wenv*0.05; R+=wr*wenv*0.05

# ---------- 远处手鼓：仅经幡场，低频闷击 ----------
def drum():
    n=int(0.9*SR); tt=np.arange(n)/SR; f=58+40*np.exp(-tt/0.05)
    return np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-tt/0.28)
for k,t0 in enumerate(np.arange(31.3,35.9,1.15)):
    add(drum(),t0,0.5,0.20*(0.8 if k%2 else 1.0))

# ---------- 混响：去相关的指数衰减噪声脉冲，FFT 卷积 ----------
def reverb(x,seed,rt=3.4):
    n=int(rt*SR); tt=np.arange(n)/SR
    ir=np.random.default_rng(seed).standard_normal(n)*np.exp(-6.91*tt/rt); ir[:int(0.03*SR)]=0; ir/=np.sqrt((ir**2).sum())
    m=1<<int(np.ceil(np.log2(len(x)+n))); y=np.fft.irfft(np.fft.rfft(x,m)*np.fft.rfft(ir,m),m)[:len(x)]
    return y
wetL,wetR=reverb(L,11),reverb(R,12)
outL=L*0.72+wetL*0.55; outR=R*0.72+wetR*0.55
fade=np.clip(t/0.4,0,1)*np.clip((T-t)/2.2,0,1)
outL*=fade; outR*=fade
peak=max(np.abs(outL).max(),np.abs(outR).max()); outL/=peak/0.89; outR/=peak/0.89
pcm=(np.stack([outL,outR],1)*32767).astype(np.int16)
with wave.open(sys.argv[1],'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print(f"wrote {sys.argv[1]}  {T:.1f}s  peak_pre_norm={peak:.3f}")
