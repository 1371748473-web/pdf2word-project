(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // --- Chart: 性能对比 ---
  var perf = echarts.init(document.getElementById('chart-perf'), null, { renderer: 'svg' });
  perf.setOption({
    animation: false,
    tooltip: { trigger: 'axis', appendToBody: true, formatter: '{b}: {c} 秒' },
    grid: { left: 60, right: 40, top: 30, bottom: 40 },
    xAxis: {
      type: 'category',
      data: ['CPU 模式', 'GPU 模式 (RTX 3060)'],
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: ink, fontSize: 13 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '秒 / 页',
      nameTextStyle: { color: muted },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [{
      type: 'bar',
      data: [
        { value: 100, itemStyle: { color: muted, opacity: 0.75, borderRadius: [6, 6, 0, 0] } },
        { value: 25, itemStyle: { color: accent, borderRadius: [6, 6, 0, 0] } }
      ],
      barWidth: '38%',
      label: { show: true, position: 'top', color: ink, fontSize: 14, fontWeight: 700, formatter: '{c} s' }
    }]
  });

  // --- Chart: 安装包体积 ---
  var size = echarts.init(document.getElementById('chart-size'), null, { renderer: 'svg' });
  size.setOption({
    animation: false,
    tooltip: { trigger: 'axis', appendToBody: true, formatter: '{b}: {c} MB' },
    grid: { left: 70, right: 40, top: 30, bottom: 50 },
    xAxis: {
      type: 'category',
      data: ['v1.2 优化前\n(GPU 版)', 'v1.2 优化后\n(GPU 完整版)', '精简版\n(Lite)'],
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: ink, fontSize: 12, interval: 0 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: 'MB',
      nameTextStyle: { color: muted },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [{
      type: 'bar',
      data: [
        { value: 1520, itemStyle: { color: muted, opacity: 0.6, borderRadius: [6, 6, 0, 0] } },
        { value: 1020.3, itemStyle: { color: accent, borderRadius: [6, 6, 0, 0] } },
        { value: 290.6, itemStyle: { color: accent2, borderRadius: [6, 6, 0, 0] } }
      ],
      barWidth: '38%',
      label: { show: true, position: 'top', color: ink, fontSize: 13, fontWeight: 700, formatter: '{c} MB' }
    }]
  });

  window.addEventListener('resize', function() {
    perf.resize();
    size.resize();
  });
})();
