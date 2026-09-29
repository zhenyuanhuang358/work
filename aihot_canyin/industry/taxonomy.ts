// 餐饮消费版分类体系（替换 AIHOT 原 industry/taxonomy.ts）。
// 类别 key 会出现在网址里（/all?category=…），上线后不要改；标签和名录可以随时增减。
// ITEM_TYPES 必须与 prompts/selection-score.md 的权重表、prompts/content-understanding.md 的类型说明同步。

export const CATEGORIES = [
  { key: "operating", label: "经营", section: "经营数据", guide: "财报、业绩预告、营运数据、招股书、官方行业统计里的同店、翻台、人均、门店数与利润率" },
  { key: "stores", label: "门店", section: "门店与加盟", guide: "开店关店、进入退出城市、店型调整、自营转加盟、加盟政策与加盟商关系" },
  { key: "price", label: "价格", section: "价格与产品", guide: "调价、套餐、新品、团购外卖价格、会员与补贴" },
  { key: "capital", label: "资本", section: "资本动作", guide: "上市申请与聆讯、融资、并购、回购分红、增减持、私有化" },
  { key: "policy", label: "规则", section: "政策、食安与平台", guide: "监管政策与处罚、食安事件、劳动税务、外卖与团购平台的佣金补贴流量规则" },
  { key: "people", label: "人事", section: "人事与组织", guide: "创始人与核心高管变动、组织调整、股权激励、裁员与劳动争议" },
  { key: "analysis", label: "观点", section: "分析与观点", guide: "行业报告、深度复盘、管理层访谈、券商观点、行业人士判断" },
  { key: "travel", label: "文旅", section: "文旅消费", guide: "主题乐园、景区、旅行社、酒店的经营与客流，节假日文旅数据" },
] as const;

export const ITEM_TYPES = [
  "operating_disclosure", "network_change", "pricing_product", "capital_event", "regulation_platform", "people_org", "analysis_opinion",
] as const;

// ── 标签词表 ────────────────────────────────────────────────────────────────────────────

/** 每篇资料的第一个标签必须是这些“分类标签”之一。 */
export const CATEGORY_TAGS = [
  "经营数据", "门店与加盟", "价格与产品", "资本动作", "政策监管", "食安", "平台规则", "人事组织", "行业分析", "文旅", "其他",
] as const;

/** 可选的主题标签：品类与经营议题。 */
export const TOPIC_TAGS = [
  "火锅", "中式正餐", "中式快餐", "西式快餐", "茶饮", "咖啡", "烘焙", "团餐", "日料", "烧烤",
  "同店", "翻台", "人均", "加盟", "下沉市场", "出海", "外卖", "团购", "预制菜", "供应链", "餐饮科技", "主题乐园", "旅行社",
] as const;

/** 可选的实体标签（只放读者最常按它筛选的几家；其余用 entity:<id> 归类）。 */
export const ENTITY_TAGS = ["海底捞", "百胜中国", "绿茶", "蜜雪", "瑞幸", "美团"] as const;

export const TAG_SYNONYMS: Readonly<Record<string, string>> = {
  财报: "经营数据", 业绩: "经营数据", 营运数据: "经营数据", 招股书: "经营数据",
  开店: "门店与加盟", 关店: "门店与加盟", 闭店: "门店与加盟", 加盟政策: "门店与加盟",
  调价: "价格与产品", 降价: "价格与产品", 涨价: "价格与产品", 新品: "价格与产品",
  融资: "资本动作", 上市: "资本动作", IPO: "资本动作", 并购: "资本动作", 收购: "资本动作", 回购: "资本动作",
  政策: "政策监管", 监管: "政策监管", 处罚: "政策监管", 食品安全: "食安",
  佣金: "平台规则", 补贴: "平台规则", 平台: "平台规则",
  人事: "人事组织", 高管: "人事组织", 组织: "人事组织",
  观点: "行业分析", 研报: "行业分析", 报告: "行业分析", 复盘: "行业分析",
  旅游: "文旅", 景区: "文旅", 乐园: "文旅",
  新茶饮: "茶饮", 奶茶: "茶饮", 现制茶饮: "茶饮", 现磨咖啡: "咖啡", 客单价: "人均", 同店销售: "同店", 翻台率: "翻台",
};

export const CATEGORY_BY_ITEM_TYPE: Readonly<Record<string, string>> = {
  operating_disclosure: "经营数据", network_change: "门店与加盟", pricing_product: "价格与产品", capital_event: "资本动作",
  regulation_platform: "政策监管", people_org: "人事组织", analysis_opinion: "行业分析",
};

// ── 公司与主体 ──────────────────────────────────────────────────────────────────────────
// 名录按用户实际研究过和客户常问的公司排。股票代码写在 aihot_canyin/README.md 的信源表里，这里只放别名。
// 别名只放“出现就几乎一定指这家公司”的词；像“肯德基”“必胜客”在海外新闻里指 Yum! Brands，
// 所以百胜中国的别名只放中国语境的写法，海外报道靠 IDENTITY_LEXICON 的原文校验兜底。

export const ENTITIES: Record<string, { name: string; displayTag: string | null; aliases: string[] }> = {
  haidilao: { name: "海底捞", displayTag: "海底捞", aliases: ["海底捞", "Haidilao", "红石榴计划", "焰请烤肉"] },
  superhi: { name: "特海国际", displayTag: null, aliases: ["特海国际", "Super Hi"] },
  yumchina: { name: "百胜中国", displayTag: "百胜中国", aliases: ["百胜中国", "Yum China", "肯德基中国", "必胜客中国"] },
  greentea: { name: "绿茶集团", displayTag: "绿茶", aliases: ["绿茶集团", "绿茶餐厅", "Green Tea Group"] },
  jiumaojiu: { name: "九毛九", displayTag: null, aliases: ["九毛九", "太二酸菜鱼", "怂火锅"] },
  xiabuxiabu: { name: "呷哺呷哺", displayTag: null, aliases: ["呷哺呷哺", "呷哺", "湊湊"] },
  xiaocaiyuan: { name: "小菜园", displayTag: null, aliases: ["小菜园"] },
  ajisen: { name: "味千中国", displayTag: null, aliases: ["味千拉面", "味千中国"] },
  sushiro: { name: "寿司郎", displayTag: null, aliases: ["寿司郎", "Sushiro", "FOOD & LIFE COMPANIES"] },
  dpc: { name: "达势股份（达美乐中国）", displayTag: null, aliases: ["达势股份", "达美乐中国", "DPC Dash"] },
  mixue: { name: "蜜雪集团", displayTag: "蜜雪", aliases: ["蜜雪集团", "蜜雪冰城", "幸运咖"] },
  guming: { name: "古茗", displayTag: null, aliases: ["古茗"] },
  chabaidao: { name: "茶百道", displayTag: null, aliases: ["茶百道"] },
  auntea: { name: "沪上阿姨", displayTag: null, aliases: ["沪上阿姨"] },
  nayuki: { name: "奈雪的茶", displayTag: null, aliases: ["奈雪的茶", "奈雪"] },
  chagee: { name: "霸王茶姬", displayTag: null, aliases: ["霸王茶姬", "CHAGEE"] },
  heytea: { name: "喜茶", displayTag: null, aliases: ["喜茶", "HEYTEA"] },
  luckin: { name: "瑞幸咖啡", displayTag: "瑞幸", aliases: ["瑞幸", "luckin"] },
  cotti: { name: "库迪咖啡", displayTag: null, aliases: ["库迪", "COTTI"] },
  guoquan: { name: "锅圈", displayTag: null, aliases: ["锅圈食汇", "锅圈"] },
  tastien: { name: "塔斯汀", displayTag: null, aliases: ["塔斯汀"] },
  laoxiangji: { name: "老乡鸡", displayTag: null, aliases: ["老乡鸡"] },
  banu: { name: "巴奴毛肚火锅", displayTag: null, aliases: ["巴奴"] },
  tongqinglou: { name: "同庆楼", displayTag: null, aliases: ["同庆楼"] },
  quanjude: { name: "全聚德", displayTag: null, aliases: ["全聚德"] },
  meituan: { name: "美团", displayTag: "美团", aliases: ["美团", "大众点评", "美团外卖"] },
  haichang: { name: "海昌海洋公园", displayTag: null, aliases: ["海昌海洋公园", "Haichang Ocean Park"] },
  chimelong: { name: "长隆集团", displayTag: null, aliases: ["长隆"] },
  utour: { name: "众信旅游", displayTag: null, aliases: ["众信旅游", "众信博睿"] },
};

/** 摘要和标题里出现的公司必须在原文里出现过，否则退回原标题（防张冠李戴，如把“某火锅龙头”写成海底捞）。 */
export const IDENTITY_LEXICON: ReadonlyArray<{ id: string; name: string; patterns: RegExp[] }> = Object.entries(ENTITIES).map(
  ([id, e]) => ({ id, name: e.name, patterns: [new RegExp(e.aliases.map((a) => a.replace(/[.*+?^${}()|[\]\\&]/g, "\\$&")).join("|"), "i")] }),
);

/** 这些域名上的文章，发布方就是对应的公司。 */
export const PUBLISHER_DOMAINS: ReadonlyArray<{ entityId: string; domains: readonly string[] }> = [];

export const IDENTITY_CONTEXT_ALIASES: ReadonlyArray<{ entityId: string; pattern: RegExp }> = [];
