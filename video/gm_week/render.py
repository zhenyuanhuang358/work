"""渲染器：逐帧调用 film.html 的 render(t)，取 canvas PNG，交给 ffmpeg 编码 H.264。
用法：python3 render.py START END OUT.mp4 [--fps 30]   或   python3 render.py --sheet OUT.png（九帧取样）"""
import sys, base64, subprocess, pathlib, tempfile, argparse, json
from playwright.sync_api import sync_playwright
import imageio_ffmpeg
HERE=pathlib.Path(__file__).resolve().parent
FF=imageio_ffmpeg.get_ffmpeg_exe()

def frames(times, outdir):
    over=[]
    with sync_playwright() as p:
        b=p.chromium.launch(); pg=b.new_page(viewport={"width":1080,"height":1920})
        pg.goto((HERE/"film.html").as_uri()); pg.wait_for_timeout(300)
        for k,t in enumerate(times):
            o=pg.evaluate(f"window.render({t})")
            if o: over.append({"t":round(t,3),"items":o})
            data=pg.evaluate("document.getElementById('c').toDataURL('image/png')").split(",",1)[1]
            (outdir/f"f{k:05d}.png").write_bytes(base64.b64decode(data))
        b.close()
    return over

ap=argparse.ArgumentParser(); ap.add_argument("start",nargs="?",type=float); ap.add_argument("end",nargs="?",type=float)
ap.add_argument("out"); ap.add_argument("--fps",type=int,default=30); ap.add_argument("--sheet",action="store_true")
a=ap.parse_args()
with tempfile.TemporaryDirectory() as td:
    td=pathlib.Path(td)
    if a.sheet:
        ts=[0.6,2.2,4.9,11.0,18.5,25.8,32.8,39.2,44.6]
        over=frames(ts,td)
        subprocess.run([FF,"-y","-loglevel","error","-i",str(td/"f%05d.png"),"-vf","scale=360:640,tile=3x3:padding=12:color=0x0a0a0b","-frames:v","1",a.out],check=True)
    else:
        n=round((a.end-a.start)*a.fps); ts=[a.start+i/a.fps for i in range(n)]
        over=frames(ts,td)
        subprocess.run([FF,"-y","-loglevel","error","-framerate",str(a.fps),"-i",str(td/"f%05d.png"),
                        "-c:v","libx264","-pix_fmt","yuv420p","-crf","20","-movflags","+faststart",a.out],check=True)
print(json.dumps({"out":a.out,"overflow_frames":len(over),"overflow_sample":over[:3]},ensure_ascii=False))
