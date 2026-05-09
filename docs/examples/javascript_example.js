// CityFlow API JavaScript 示例
// 适用于浏览器环境和 Node.js 18+

const BASE_URL = "http://localhost:8000";

/**
 * 规划路线 - 流式SSE响应
 */
async function planRoute(userInput) {
  const response = await fetch(`${BASE_URL}/api/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_input: userInput }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split("\n");

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = JSON.parse(line.slice(6));
        console.log(`[${data.type || "event"}]`, data);
      }
    }
  }
}

/**
 * 搜索POI
 */
async function searchPOIs(region, category = null) {
  const body = { region };
  if (category) body.categories = [category];

  const response = await fetch(`${BASE_URL}/api/poi/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  const pois = data.pois || [];
  console.log(`找到 ${pois.length} 个POI:`);
  pois.forEach((poi) => console.log(`  - ${poi.name} (${poi.category})`));
  return pois;
}

/**
 * 获取POI详情
 */
async function getPOIDetail(poiId) {
  const response = await fetch(`${BASE_URL}/api/poi/detail/${poiId}`);
  const data = await response.json();
  console.log("POI详情:", JSON.stringify(data, null, 2));
  return data;
}

/**
 * 计算距离矩阵
 */
async function calculateDistance(poiIds) {
  const response = await fetch(`${BASE_URL}/api/poi/distance-matrix`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ poi_ids: poiIds }),
  });

  const data = await response.json();
  console.log("距离矩阵:", JSON.stringify(data, null, 2));
  return data;
}

/**
 * 调整路线 - 对话式交互
 */
async function adjustRoute(routeId, instruction) {
  const response = await fetch(`${BASE_URL}/api/dialogue/${routeId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction }),
  });

  const data = await response.json();
  console.log("调整结果:", data.reply);
  return data;
}

// 使用示例
(async () => {
  // 1. 规划路线
  console.log("=== 规划路线 ===");
  await planRoute("周末想一个人安静走走");

  // 2. 搜索POI
  console.log("\n=== 搜索POI ===");
  await searchPOIs("珠海", "文化");

  // 3. 调整路线 (需要有效的routeId)
  // await adjustRoute("your-route-id", "太赶了，想轻松点");
})();
