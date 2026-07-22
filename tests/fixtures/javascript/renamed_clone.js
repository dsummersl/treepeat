function seriesDataOld(wellId) {
  if (wellId === "all") {
    return years.flatMap(y => (cy[String(y)] || []).map((v, m) => (v != null ? { y, m, v } : null)).filter(Boolean));
  }
  const s = sw[wellId] || {};
  return years.flatMap(y => (s[String(y)] || []).map((v, m) => (v != null ? { y, m, v } : null)).filter(Boolean));
}

function seriesData(wellId) {
  if (wellId === "all") {
    return years.flatMap(y => (cy[String(y)] || []).map((v, m) => (v != null ? { y, m, v } : null)).filter(Boolean));
  }
  const s = sw[wellId] || {};
  return years.flatMap(y => (s[String(y)] || []).map((v, m) => (v != null ? { y, m, v } : null)).filter(Boolean));
}
