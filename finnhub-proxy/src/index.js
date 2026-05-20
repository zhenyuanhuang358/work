export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const symbols = url.searchParams.get("symbols") || url.searchParams.get("symbol") || "SPY";

    // 支持批量查询：?symbols=SPY,QQQ,NVDA
    const tickers = symbols.split(",").map(s => s.trim().toUpperCase());

    const results = {};
    await Promise.all(
      tickers.map(async (ticker) => {
        const resp = await fetch(
          `https://finnhub.io/api/v1/quote?symbol=${ticker}&token=${env.FINNHUB_TOKEN}`
        );
        const data = await resp.json();
        results[ticker] = {
          price: data.c,
          change: data.d,
          changePct: data.dp,
          high: data.h,
          low: data.l,
          prevClose: data.pc,
        };
      })
    );

    return new Response(JSON.stringify(results), {
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
    });
  },
};
