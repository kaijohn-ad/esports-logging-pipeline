import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Bar } from 'react-chartjs-2';

const PlayerComparison = () => {
  const [players, setPlayers] = useState([]);
  const [selectedPlayers, setSelectedPlayers] = useState([]);
  const [comparisonData, setComparisonData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // プレイヤーリストを取得
  useEffect(() => {
    const fetchPlayers = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/players');
        setPlayers(response.data.players);
      } catch (err) {
        setError('プレイヤーデータの取得に失敗しました');
        console.error('Error fetching players:', err);
      }
    };

    fetchPlayers();
  }, []);

  // 比較データを取得
  const fetchComparisonData = async () => {
    if (selectedPlayers.length < 2) return;

    setLoading(true);
    setError(null);

    try {
      const playerIds = selectedPlayers.map(p => p.id).join(',');
      const response = await axios.get(`http://localhost:8000/api/players/compare?player_ids=${playerIds}`);
      setComparisonData(response.data);
    } catch (err) {
      setError('比較データの取得に失敗しました');
      console.error('Error fetching comparison data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handlePlayerToggle = (player) => {
    setSelectedPlayers(prev => {
      const isSelected = prev.find(p => p.id === player.id);
      if (isSelected) {
        return prev.filter(p => p.id !== player.id);
      } else if (prev.length < 5) {
        return [...prev, player];
      }
      return prev;
    });
  };

  const getChartData = () => {
    if (!comparisonData) return null;

    const labels = selectedPlayers.map(p => p.name);
    const kdaData = comparisonData.comparison.map(p => p.data.kda || 0);
    const csData = comparisonData.comparison.map(p => p.data.cs_per_10min || 0);
    const goldData = comparisonData.comparison.map(p => p.data.gold_per_min || 0);

    return {
      labels,
      datasets: [
        {
          label: 'KDA',
          data: kdaData,
          backgroundColor: 'rgba(59, 130, 246, 0.8)',
          borderColor: 'rgba(59, 130, 246, 1)',
          borderWidth: 1,
        },
        {
          label: 'CS/10分',
          data: csData,
          backgroundColor: 'rgba(16, 185, 129, 0.8)',
          borderColor: 'rgba(16, 185, 129, 1)',
          borderWidth: 1,
        },
        {
          label: 'ゴールド/分',
          data: goldData,
          backgroundColor: 'rgba(245, 158, 11, 0.8)',
          borderColor: 'rgba(245, 158, 11, 1)',
          borderWidth: 1,
        },
      ],
    };
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: 'プレイヤー比較',
      },
    },
    scales: {
      y: {
        beginAtZero: true,
      },
    },
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">プレイヤー比較</h1>
        <p className="text-gray-600">複数のプレイヤーのパフォーマンスを比較分析</p>
      </div>

      {/* プレイヤー選択 */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          プレイヤー選択 ({selectedPlayers.length}/5)
        </h2>
        
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {players.map((player) => {
            const isSelected = selectedPlayers.find(p => p.id === player.id);
            const isDisabled = !isSelected && selectedPlayers.length >= 5;
            
            return (
              <button
                key={player.id}
                onClick={() => handlePlayerToggle(player)}
                disabled={isDisabled}
                className={`p-4 rounded-lg border-2 transition-all duration-200 ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : isDisabled
                    ? 'border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed'
                    : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
                }`}
              >
                <div className="font-medium">{player.name}</div>
                {isSelected && (
                  <div className="text-sm text-blue-600 mt-1">選択済み</div>
                )}
              </button>
            );
          })}
        </div>

        <div className="mt-6 flex justify-between items-center">
          <div className="text-sm text-gray-500">
            {selectedPlayers.length >= 2 ? '比較可能' : '2人以上のプレイヤーを選択してください'}
          </div>
          
          <div className="flex gap-3">
            <button
              onClick={() => setSelectedPlayers([])}
              className="button-secondary"
              disabled={selectedPlayers.length === 0}
            >
              選択解除
            </button>
            
            <button
              onClick={fetchComparisonData}
              disabled={selectedPlayers.length < 2 || loading}
              className="button-primary disabled:opacity-50"
            >
              {loading ? '比較中...' : '比較開始'}
            </button>
          </div>
        </div>
      </div>

      {/* エラー表示 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-8">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* 比較結果 */}
      {comparisonData && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* チャート */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">パフォーマンス比較</h2>
              <div className="chart-container">
                <Bar data={getChartData()} options={chartOptions} />
              </div>
            </div>
          </div>

          {/* 詳細統計 */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">詳細統計</h2>
              <div className="space-y-4">
                {comparisonData.comparison.map((player, index) => (
                  <div key={index} className="border-b border-gray-200 pb-4 last:border-b-0">
                    <div className="font-medium text-gray-900 mb-2">
                      {selectedPlayers.find(p => p.id === player.player_id)?.name || player.player_id}
                    </div>
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span>KDA:</span>
                        <span className="font-medium">{player.data.kda || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>CS/10分:</span>
                        <span className="font-medium">{player.data.cs_per_10min || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>ゴールド/分:</span>
                        <span className="font-medium">{player.data.gold_per_min || 0}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 比較データ未取得時のメッセージ */}
      {!comparisonData && selectedPlayers.length >= 2 && !loading && (
        <div className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">比較データを取得</h3>
          <p className="mt-1 text-sm text-gray-500">
            「比較開始」ボタンをクリックして、選択したプレイヤーのデータを比較してください。
          </p>
        </div>
      )}
    </div>
  );
};

export default PlayerComparison;