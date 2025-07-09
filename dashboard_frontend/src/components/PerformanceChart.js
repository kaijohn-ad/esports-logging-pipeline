import React, { useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  BarElement,
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';

// Chart.jsの設定
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const PerformanceChart = ({ performanceData, loading }) => {
  const [activeChart, setActiveChart] = useState('kda');

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">パフォーマンス推移</h2>
          <div className="flex space-x-2">
            {['KDA', 'CS', 'ゴールド'].map((label) => (
              <div key={label} className="h-8 w-16 bg-gray-200 rounded animate-pulse"></div>
            ))}
          </div>
        </div>
        <div className="chart-container">
          <div className="w-full h-full bg-gray-200 rounded animate-pulse"></div>
        </div>
      </div>
    );
  }

  if (!performanceData || !performanceData.performance) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">パフォーマンス推移</h2>
        <div className="chart-container flex items-center justify-center">
          <p className="text-gray-500">パフォーマンスデータが利用できません</p>
        </div>
      </div>
    );
  }

  const { performance } = performanceData;

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      tooltip: {
        mode: 'index',
        intersect: false,
      },
    },
    scales: {
      x: {
        display: true,
        title: {
          display: true,
          text: '直近の試合'
        }
      },
      y: {
        display: true,
        title: {
          display: true,
          text: '値'
        }
      }
    },
    elements: {
      line: {
        tension: 0.1
      },
      point: {
        radius: 4,
        hoverRadius: 6
      }
    }
  };

  const labels = Array.from({ length: 5 }, (_, i) => `試合 ${i + 1}`);

  const kdaData = {
    labels,
    datasets: [
      {
        label: 'KDA',
        data: performance.kda_trend || [0, 0, 0, 0, 0],
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
      },
    ],
  };

  const csData = {
    labels,
    datasets: [
      {
        label: 'CS/10分',
        data: performance.cs_trend || [0, 0, 0, 0, 0],
        borderColor: 'rgb(16, 185, 129)',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        fill: true,
      },
    ],
  };

  const goldData = {
    labels,
    datasets: [
      {
        label: 'ゴールド/分',
        data: performance.gold_trend || [0, 0, 0, 0, 0],
        borderColor: 'rgb(245, 158, 11)',
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        fill: true,
      },
    ],
  };

  const combinedData = {
    labels,
    datasets: [
      {
        label: 'KDA',
        data: performance.kda_trend || [0, 0, 0, 0, 0],
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        yAxisID: 'y',
      },
      {
        label: 'CS/10分',
        data: performance.cs_trend || [0, 0, 0, 0, 0],
        borderColor: 'rgb(16, 185, 129)',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        yAxisID: 'y1',
      },
    ],
  };

  const combinedOptions = {
    ...chartOptions,
    scales: {
      ...chartOptions.scales,
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        title: {
          display: true,
          text: 'KDA'
        }
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        title: {
          display: true,
          text: 'CS/10分'
        },
        grid: {
          drawOnChartArea: false,
        },
      },
    },
  };

  const getChartData = () => {
    switch (activeChart) {
      case 'kda':
        return kdaData;
      case 'cs':
        return csData;
      case 'gold':
        return goldData;
      case 'combined':
        return combinedData;
      default:
        return kdaData;
    }
  };

  const getChartOptions = () => {
    return activeChart === 'combined' ? combinedOptions : chartOptions;
  };

  const chartTypes = [
    { key: 'kda', label: 'KDA', color: 'bg-blue-500' },
    { key: 'cs', label: 'CS', color: 'bg-green-500' },
    { key: 'gold', label: 'ゴールド', color: 'bg-yellow-500' },
    { key: 'combined', label: '複合', color: 'bg-purple-500' },
  ];

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 sm:mb-0">パフォーマンス推移</h2>
        
        <div className="flex flex-wrap gap-2">
          {chartTypes.map((type) => (
            <button
              key={type.key}
              onClick={() => setActiveChart(type.key)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors duration-200 ${
                activeChart === type.key
                  ? `${type.color} text-white`
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {type.label}
            </button>
          ))}
        </div>
      </div>

      <div className="chart-container">
        <Line data={getChartData()} options={getChartOptions()} />
      </div>

      {/* パフォーマンス統計 */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">勝率</div>
          <div className="text-2xl font-bold text-gray-900">
            {((performance.win_rate || 0) * 100).toFixed(1)}%
          </div>
        </div>
        
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">プレイ数</div>
          <div className="text-2xl font-bold text-gray-900">
            {performance.games_played || 0}
          </div>
        </div>
        
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm text-gray-600">平均KDA</div>
          <div className="text-2xl font-bold text-gray-900">
            {performance.kda_trend ? 
              (performance.kda_trend.reduce((a, b) => a + b, 0) / performance.kda_trend.length).toFixed(2) : 
              '0.00'
            }
          </div>
        </div>
      </div>
    </div>
  );
};

export default PerformanceChart;