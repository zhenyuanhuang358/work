# Source Register

| id | title | url | source_type | published_or_updated | authority_reason | use_for | key_takeaway | limits_or_cautions |
|---|---|---|---|---|---|---|---|---|
| A1 | OpenAI Prompt Engineering Guide | https://platform.openai.com/docs/guides/prompt-engineering | official | 2024 | OpenAI官方文档 | 核心结构、六大策略、最佳实践 | 明确指令、参考文本、分步推理、给模型思考时间是官方推荐的四个核心策略 | 针对GPT-4系列，GPT-5.5部分行为有调整 |
| A2 | OpenAI GPT-5 System Card | https://openai.com/index/gpt-5-system-card | official | 2025 | OpenAI官方发布 | GPT-5新能力描述、多模态、推理增强 | GPT-5具备更强的指令遵循能力和多步推理能力 | GPT-5.5为推测性后续版本 |
| P1 | Chain-of-Thought Prompting Elicits Reasoning in Large Language Models | https://arxiv.org/abs/2201.11903 | paper | 2022 | Google Brain，NeurIPS 2022 | 思维链技术原理 | 在提示词中展示分步推理过程，显著提升复杂任务准确率 | 原论文基于较早模型，现代模型效果更稳定 |
| P2 | Large Language Models are Zero-Shot Reasoners | https://arxiv.org/abs/2205.11916 | paper | 2022 | NeurIPS 2022 | Zero-shot CoT："Let's think step by step" | 仅添加"让我们一步步思考"即可激活零样本推理 | 现代模型已内化，但结构化触发仍有效 |
| P3 | Prompt Engineering: A Practical Guide | https://arxiv.org/abs/2312.16171 | paper | 2023 | 综述论文 | 提示词分类体系、技巧系统化 | 将提示词技术分为零样本、少样本、CoT、角色提示、指令提示等类别 | 截至2023年底，未覆盖GPT-5 |
| P4 | Self-Consistency Improves Chain of Thought Reasoning in Language Models | https://arxiv.org/abs/2203.11171 | paper | 2022 | Google Research | 自洽性采样策略 | 多次采样取投票结果可显著提升CoT准确率 | 消耗更多token，GPT-5.5内置部分自洽机制 |
| G1 | dair-ai/Prompt-Engineering-Guide | https://github.com/dair-ai/Prompt-Engineering-Guide | GitHub | 2024 | 40k+ stars，社区认可度高 | 技巧汇总、实例、最新进展 | 系统整理了从基础到高级的提示词技巧，含多个实用模板 | 社区维护，质量参差不齐 |
| G2 | brexhq/prompt-tutorial | https://github.com/brexhq/prompt-tutorial | GitHub | 2023 | 企业实践案例 | 企业级提示词工程实践 | 结构化输出、JSON格式控制、防幻觉策略 | 聚焦GPT-4，原则通用 |
| X1 | Ethan Mollick (@emollick) | https://x.com/emollick | X/practitioner | 2024-2025 | 沃顿商学院教授，高质量AI实践者 | 提示词实战技巧、GPT-5使用心得 | 角色设定+上下文+示例三要素组合是高效提示词核心 | 实践经验，非严格对照实验 |
| X2 | Riley Goodside (@goodside) | https://x.com/goodside | X/practitioner | 2023-2024 | Scale AI staff prompter，提示词工程师 | 高级技巧、越狱防御、格式控制 | 明确的格式约束（如"以JSON返回"）显著提升一致性 | 偏技术向 |
