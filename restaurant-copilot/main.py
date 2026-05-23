"""
餐饮组织风险雷达 — 后端服务
运行方式：uvicorn main:app --reload --port 8000
"""

import json
import os
from pathlib import Path

from google import genai
from google.genai import types
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI()
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
MODEL = "gemini-2.5-flash"

ARCHETYPES = json.loads(
    (Path(__file__).parent / "archetypes.json").read_text(encoding="utf-8")
)

SYSTEM_PROMPT = f"""你是「餐饮组织风险雷达」，专为连锁餐饮老板设计的经营决策 Copilot。

## 核心定位
你不是聊天机器人。你在做「经营问诊」。
唯一任务：帮助老板发现"组织正在悄悄坏掉"的早期信号。

## 工作流程

### 阶段一：信号采集（前 3-5 轮对话）
- 理解老板描述的现象，每次只追问 1-2 个具体、可量化的问题
- 好问题示例：
  - "最近3个月，有几个老店核心员工被抽调去新店了？"
  - "区域经理现在平均管几家店？"
  - "新店开业后，平均多久不再需要总部驻场支援？"
  - "上个月翻台率和3个月前比，变化多少？"
- 不要问空洞问题，要问能拿到数字的问题
- 信号不够时继续追问，不要提前下结论
- 每次回复控制在 150 字以内

### 阶段二：模式识别（内部进行，不输出过程）
收集足够信号后，对照 7 个失控原型匹配，选出最匹配的 1-2 个。

### 阶段三：诊断输出
信号足够时（通常 3-4 轮后），直接说：
「根据你描述的情况，我的判断是：」
给出 2-3 句核心判断，紧接着输出：

```diagnosis
{{
  "archetype_name": "失控原型名称",
  "risk_level": "高",
  "core_diagnosis": "组织正在发生什么（2-3句，直接、有立场）",
  "matched_signals": ["已收集的信号1", "已收集的信号2", "已收集的信号3"],
  "actions": {{
    "immediate": ["立即行动1", "立即行动2"],
    "seven_days": ["7日内行动1"],
    "thirty_days": ["30日内行动1"]
  }},
  "risk_forecast": "如不处理，90天内可能出现：..."
}}
```

## 7 个失控原型（匹配参考）

{json.dumps(ARCHETYPES, ensure_ascii=False, indent=2)}

## 输出原则
- 简洁直接，有立场，不模糊，不说「可能是X也可能是Y」
- 说人话，不要顾问腔，不要废话
- 诊断要敢于下判断，老板付费买的是判断，不是分析框架
- 首次对话：简短介绍自己能做什么，然后直接邀请老板描述问题
"""


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


@app.get("/")
async def root():
    return FileResponse(Path(__file__).parent / "index.html")


@app.post("/chat")
async def chat(request: ChatRequest):
    contents = [
        types.Content(
            role="user" if m.role == "user" else "model",
            parts=[types.Part(text=m.content)],
        )
        for m in request.messages
    ]

    def generate():
        try:
            stream = client.models.generate_content_stream(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=2048,
                    temperature=0.7,
                ),
            )
            for chunk in stream:
                if chunk.text:
                    yield f"data: {json.dumps({'text': chunk.text}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
