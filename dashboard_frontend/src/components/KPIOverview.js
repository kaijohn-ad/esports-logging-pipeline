import React from 'react';

const KPIOverview = ({ kpiData, loading }) => {
  if (loading) {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-900">KPI 概要</h2>
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="metric-card animate-pulse">
              <div className="h-4 bg-gray-200 rounded mb-2"></div>
              <div className="h-8 bg-gray-200 rounded"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!kpiData || !kpiData.summary) {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-900">KPI 概要</h2>
        <div className="metric-card">
          <p className="text-gray-500">KPIデータが利用できません</p>
        </div>
      </div>
    );
  }

  const { summary } = kpiData;

  const metrics = [
    {
      label: 'KDA',
      value: summary.avg_kda?.toFixed(2) || '0.00',
      trend: summary.avg_kda > 2 ? 'up' : summary.avg_kda < 1 ? 'down' : 'neutral',
      description: 'キル/デス/アシスト比'
    },
    {
      label: 'CS/10分',
      value: summary.avg_cs_per_10min?.toFixed(1) || '0.0',
      trend: summary.avg_cs_per_10min > 7 ? 'up' : summary.avg_cs_per_10min < 5 ? 'down' : 'neutral',
      description: '10分あたりのクリープスコア'
    },
    {
      label: 'ゴールド/分',
      value: summary.avg_gold_per_min?.toFixed(0) || '0',
      trend: summary.avg_gold_per_min > 400 ? 'up' : summary.avg_gold_per_min < 300 ? 'down' : 'neutral',
      description: '1分あたりのゴールド獲得量'
    },
    {
      label: '総試合数',
      value: summary.total_games || '0',
      trend: 'neutral',
      description: '集計期間内の試合数'
    }
  ];

  const getTrendIcon = (trend) => {
    switch (trend) {
      case 'up':
        return (
          <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        );
      case 'down':
        return (
          <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
          </svg>
        );
      default:
        return (
          <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
          </svg>
        );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">KPI 概要</h2>
        <div className="text-sm text-gray-500">
          {summary.total_games} 試合の平均
        </div>
      </div>

      <div className="space-y-4">
        {metrics.map((metric, index) => (
          <div key={index} className="metric-card">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="metric-label">{metric.label}</div>
                <div className="metric-value">{metric.value}</div>
                <div className="text-xs text-gray-500 mt-1">{metric.description}</div>
              </div>
              <div className="flex-shrink-0">
                {getTrendIcon(metric.trend)}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 最新の試合KPI */}
      {kpiData.kpi_data && kpiData.kpi_data.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-900 mb-3">最新の試合</h3>
          <div className="space-y-2">
            {kpiData.kpi_data.slice(0, 3).map((match, index) => (
              <div key={index} className="flex justify-between items-center text-sm">
                <span className="text-gray-600 truncate">
                  {match.kpi.champion || 'Unknown'}
                </span>
                <span className="font-medium">
                  KDA: {match.kpi.kda}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default KPIOverview;