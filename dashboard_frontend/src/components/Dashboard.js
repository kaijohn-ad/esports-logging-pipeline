import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import PlayerSelection from './PlayerSelection';
import KPIOverview from './KPIOverview';
import PerformanceChart from './PerformanceChart';
import RecentMatches from './RecentMatches';
import { useWebSocket } from '../hooks/useWebSocket';

const Dashboard = () => {
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [players, setPlayers] = useState([]);
  const [kpiData, setKpiData] = useState(null);
  const [performanceData, setPerformanceData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const { connectionStatus, lastMessage } = useWebSocket(
    selectedPlayer ? `ws://localhost:8000/ws/${selectedPlayer.id}` : null
  );

  // プレイヤーリストを取得
  useEffect(() => {
    const fetchPlayers = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/players');
        setPlayers(response.data.players);
        // デフォルトで最初のプレイヤーを選択
        if (response.data.players.length > 0) {
          setSelectedPlayer(response.data.players[0]);
        }
      } catch (err) {
        setError('プレイヤーデータの取得に失敗しました');
        console.error('Error fetching players:', err);
      }
    };

    fetchPlayers();
  }, []);

  // 選択されたプレイヤーのデータを取得
  useEffect(() => {
    if (!selectedPlayer) return;

    const fetchPlayerData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // KPIデータを取得
        const kpiResponse = await axios.get(
          `http://localhost:8000/api/players/${selectedPlayer.id}/kpi`
        );
        setKpiData(kpiResponse.data);

        // パフォーマンスデータを取得
        const performanceResponse = await axios.get(
          `http://localhost:8000/api/players/${selectedPlayer.id}/performance`
        );
        setPerformanceData(performanceResponse.data);

      } catch (err) {
        setError('プレイヤーデータの取得に失敗しました');
        console.error('Error fetching player data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPlayerData();
  }, [selectedPlayer]);

  // WebSocketメッセージを処理
  useEffect(() => {
    if (lastMessage) {
      const data = JSON.parse(lastMessage.data);
      
      if (data.type === 'kpi_update') {
        // KPIデータを更新
        setKpiData(prev => ({
          ...prev,
          summary: data.data
        }));
      }
    }
  }, [lastMessage]);

  const handlePlayerSelect = (player) => {
    setSelectedPlayer(player);
  };

  const handleRefresh = () => {
    if (selectedPlayer) {
      // データを再取得
      const fetchData = async () => {
        setLoading(true);
        try {
          const [kpiResponse, performanceResponse] = await Promise.all([
            axios.get(`http://localhost:8000/api/players/${selectedPlayer.id}/kpi`),
            axios.get(`http://localhost:8000/api/players/${selectedPlayer.id}/performance`)
          ]);
          
          setKpiData(kpiResponse.data);
          setPerformanceData(performanceResponse.data);
        } catch (err) {
          setError('データの更新に失敗しました');
        } finally {
          setLoading(false);
        }
      };
      
      fetchData();
    }
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          プレイヤーパフォーマンス ダッシュボード
        </h1>
        <p className="text-gray-600">
          リアルタイムでプレイヤーの統計情報とパフォーマンスメトリクスを確認
        </p>
      </div>

      {/* プレイヤー選択とアクション */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-8">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div className="flex-1 min-w-0">
            <PlayerSelection
              players={players}
              selectedPlayer={selectedPlayer}
              onPlayerSelect={handlePlayerSelect}
            />
          </div>
          
          <div className="flex items-center gap-3">
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
              {connectionStatus === 'connected' ? '接続中' :
               connectionStatus === 'connecting' ? '接続中...' :
               '切断'}
            </div>
            
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="button-primary disabled:opacity-50"
            >
              {loading ? '更新中...' : '更新'}
            </button>
            
            {selectedPlayer && (
              <Link
                to={`/player/${selectedPlayer.id}`}
                className="button-secondary"
              >
                詳細表示
              </Link>
            )}
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

      {/* メインコンテンツ */}
      {selectedPlayer && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 左側: KPI概要 */}
          <div className="lg:col-span-1">
            <KPIOverview 
              kpiData={kpiData}
              loading={loading}
            />
          </div>

          {/* 右側: パフォーマンスチャートと最近の試合 */}
          <div className="lg:col-span-2 space-y-8">
            <PerformanceChart 
              performanceData={performanceData}
              loading={loading}
            />
            
            <RecentMatches 
              playerId={selectedPlayer.id}
              loading={loading}
            />
          </div>
        </div>
      )}

      {/* プレイヤー未選択時のメッセージ */}
      {!selectedPlayer && !loading && players.length === 0 && (
        <div className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-2.239" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">プレイヤーデータなし</h3>
          <p className="mt-1 text-sm text-gray-500">
            まだプレイヤーデータが登録されていません。
          </p>
        </div>
      )}
    </div>
  );
};

export default Dashboard;