import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import KPIOverview from './KPIOverview';
import PerformanceChart from './PerformanceChart';
import RecentMatches from './RecentMatches';
import { useWebSocket } from '../hooks/useWebSocket';

const PlayerDetail = () => {
  const { playerId } = useParams();
  const [playerData, setPlayerData] = useState(null);
  const [kpiData, setKpiData] = useState(null);
  const [performanceData, setPerformanceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeRange, setTimeRange] = useState('week');

  const { connectionStatus, lastMessage } = useWebSocket(
    playerId ? `ws://localhost:8000/ws/${playerId}` : null
  );

  useEffect(() => {
    if (!playerId) return;

    const fetchPlayerData = async () => {
      setLoading(true);
      setError(null);

      try {
        // プレイヤーの基本情報を取得
        const playersResponse = await axios.get('http://localhost:8000/api/players');
        const player = playersResponse.data.players.find(p => p.id === playerId);
        
        if (!player) {
          throw new Error('プレイヤーが見つかりません');
        }
        
        setPlayerData(player);

        // KPIデータを取得
        const kpiResponse = await axios.get(
          `http://localhost:8000/api/players/${playerId}/kpi`
        );
        setKpiData(kpiResponse.data);

        // パフォーマンスデータを取得
        const performanceResponse = await axios.get(
          `http://localhost:8000/api/players/${playerId}/performance?time_range=${timeRange}`
        );
        setPerformanceData(performanceResponse.data);

      } catch (err) {
        setError(err.message || 'データの取得に失敗しました');
        console.error('Error fetching player data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPlayerData();
  }, [playerId, timeRange]);

  // WebSocketメッセージを処理
  useEffect(() => {
    if (lastMessage) {
      const data = JSON.parse(lastMessage.data);
      
      if (data.type === 'kpi_update') {
        setKpiData(prev => ({
          ...prev,
          summary: data.data
        }));
      }
    }
  }, [lastMessage]);

  const handleTimeRangeChange = (newRange) => {
    setTimeRange(newRange);
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded mb-4"></div>
          <div className="h-4 bg-gray-200 rounded mb-8"></div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1">
              <div className="h-96 bg-gray-200 rounded"></div>
            </div>
            <div className="lg:col-span-2">
              <div className="h-96 bg-gray-200 rounded"></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">エラー</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
        
        <div className="mt-8 text-center">
          <Link to="/" className="button-primary">
            ダッシュボードに戻る
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* ヘッダー */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              {playerData?.name || playerId}
            </h1>
            <p className="text-gray-600 mt-1">
              プレイヤー詳細パフォーマンス分析
            </p>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className={`websocket-indicator ${
              connectionStatus === 'connected' ? 'websocket-connected' :
              connectionStatus === 'connecting' ? 'websocket-connecting' :
              'websocket-disconnected'
            }`}>
              <span className={`w-2 h-2 rounded-full mr-2 ${
                connectionStatus === 'connected' ? 'bg-green-500' :
                connectionStatus === 'connecting' ? 'bg-yellow-500' :
                'bg-red-500'
              }`}></span>
              {connectionStatus === 'connected' ? 'リアルタイム更新中' :
               connectionStatus === 'connecting' ? '接続中...' :
               'オフライン'}
            </div>
            
            <Link to="/" className="button-secondary">
              ダッシュボードに戻る
            </Link>
          </div>
        </div>
      </div>

      {/* 時間範囲選択 */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 sm:mb-0">
            分析期間
          </h2>
          
          <div className="flex space-x-2">
            {[
              { key: 'day', label: '1日' },
              { key: 'week', label: '1週間' },
              { key: 'month', label: '1ヶ月' },
            ].map((range) => (
              <button
                key={range.key}
                onClick={() => handleTimeRangeChange(range.key)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors duration-200 ${
                  timeRange === range.key
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                {range.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* メインコンテンツ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* 左側: KPI概要 */}
        <div className="lg:col-span-1">
          <KPIOverview 
            kpiData={kpiData}
            loading={false}
          />
        </div>

        {/* 右側: パフォーマンスチャートと最近の試合 */}
        <div className="lg:col-span-2 space-y-8">
          <PerformanceChart 
            performanceData={performanceData}
            loading={false}
          />
          
          <RecentMatches 
            playerId={playerId}
            loading={false}
          />
          
          {/* 追加統計 */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              詳細統計 ({timeRange === 'day' ? '1日' : timeRange === 'week' ? '1週間' : '1ヶ月'})
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-sm text-gray-600">チャンピオン使用率</div>
                  <div className="mt-2 space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm">Jinx</span>
                      <span className="text-sm font-medium">45%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="bg-blue-600 h-2 rounded-full" style={{ width: '45%' }}></div>
                    </div>
                  </div>
                </div>
                
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-sm text-gray-600">ポジション別勝率</div>
                  <div className="mt-2 space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm">ADC</span>
                      <span className="text-sm font-medium">68%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">MID</span>
                      <span className="text-sm font-medium">52%</span>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="space-y-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-sm text-gray-600">最高記録</div>
                  <div className="mt-2 space-y-1">
                    <div className="flex justify-between">
                      <span className="text-sm">最高KDA</span>
                      <span className="text-sm font-medium">15.0</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">最高CS/10分</span>
                      <span className="text-sm font-medium">8.5</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">最高ゴールド/分</span>
                      <span className="text-sm font-medium">485</span>
                    </div>
                  </div>
                </div>
                
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-sm text-gray-600">最近の傾向</div>
                  <div className="mt-2">
                    <div className="flex items-center space-x-2">
                      <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                      </svg>
                      <span className="text-sm text-green-700">KDA上昇傾向</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PlayerDetail;