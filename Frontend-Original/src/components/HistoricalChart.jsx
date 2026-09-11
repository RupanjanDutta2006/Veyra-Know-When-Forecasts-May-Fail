import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const chartAreaFramePlugin = {
  id: 'chartAreaFramePlugin',
  afterDraw(chart) {
    const { ctx, chartArea } = chart;
    if (!chartArea) return;
    ctx.save();
    ctx.strokeStyle = '#374151';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(chartArea.left, chartArea.top, chartArea.right - chartArea.left, chartArea.bottom - chartArea.top);
    ctx.restore();
  },
};

export default function HistoricalChart({ data }) {
  const p1Name = data?.provider_1_name || 'NCMRWF / IMD (NEPS)';
  const p2Name = data?.provider_2_name || 'ECMWF IFS (Global ENS)';

  const ts = data?.timeseries || [
    { date_label: '01 Jun', year_label: '2026', provider_1: 0.12, provider_2: 0.14 },
    { date_label: '20 Jun', year_label: '2026', provider_1: 0.18, provider_2: 0.16 },
    { date_label: '10 Jul', year_label: '2026', provider_1: 0.22, provider_2: 0.25 },
    { date_label: '01 Aug', year_label: '2026', provider_1: 0.15, provider_2: 0.19 },
    { date_label: '20 Aug', year_label: '2026', provider_1: 0.11, provider_2: 0.13 },
  ];

  const labels = ts.map((d) => [d.date_label || '', d.year_label || '']);
  const chartData = {
    labels,
    datasets: [
      {
        label: p1Name,
        data: ts.map((d) => d.provider_1),
        borderColor: '#0044ff',
        borderWidth: 2,
        pointRadius: 2,
        pointHoverRadius: 5,
        tension: 0.15,
      },
      {
        label: p2Name,
        data: ts.map((d) => d.provider_2),
        borderColor: '#e60000',
        borderWidth: 2,
        pointRadius: 2,
        pointHoverRadius: 5,
        tension: 0.15,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    layout: { padding: { top: 6, bottom: 4, left: 4, right: 8 } },
    scales: {
      y: {
        min: 0.06,
        max: 0.30,
        ticks: {
          stepSize: 0.06,
          color: '#111827',
          font: { size: 10, weight: 'bold' },
          callback: (val) => Number(val).toFixed(2),
        },
        grid: { drawOnChartArea: false, color: '#374151' },
      },
      x: {
        ticks: {
          maxRotation: 0,
          color: '#111827',
          font: { size: 9, weight: 'bold' },
        },
        grid: { drawOnChartArea: false, color: '#374151' },
      },
    },
    plugins: { legend: { display: false } },
  };

  return (
    <div className="historical-chart-panel">
      <div className="historical-chart-header">
        BUST PROBABILITY IN LAST 3 MONTHS (90-DAY MULTI-PROVIDER AUDIT)
      </div>
      <div className="historical-chart-flex">
        <div className="historical-chart-legend">
          <div className="legend-item">
            <span className="legend-swatch" style={{ background: '#0044ff' }}></span>
            <span className="legend-label">{p1Name}</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch" style={{ background: '#e60000' }}></span>
            <span className="legend-label">{p2Name}</span>
          </div>
        </div>
        <div className="historical-chart-canvas-wrap">
          <Line data={chartData} options={options} plugins={[chartAreaFramePlugin]} />
        </div>
      </div>
    </div>
  );
}
