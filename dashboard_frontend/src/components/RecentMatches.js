import React from 'react';

const RecentMatches = ({ playerId, loading }) => {
  // 模擬データ（実際のAPIからデータを取得する場合は置き換える）
  const mockMatches = [
    {
      id: 'match1',
      date: '2025-01-21',
      champion: 'Jinx',
      result: 'Win',
      kda: '8/3/12',
      duration: '28:45',
      cs: 185
    },
    {
      id: 'match2',
      date: '2025-01-21',
      champion: 'Ashe',
      result: 'Loss',
      kda: '4/6/8',
      duration: '32:15',
      cs: 158
    },
    {
      id: 'match3',
      date: '2025-01-20',
      champion: 'Caitlyn',
      result: 'Win',
      kda: '12/2/6',
      duration: '24:30',
      cs: 167
    }
  ];

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">最近の試合</h2>
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg animate-pulse">
              <div className="flex items-center space-x-4">
                <div className="w-10 h-10 bg-gray-200 rounded-full"></div>
                <div className="space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-20"></div>
                  <div className="h-3 bg-gray-200 rounded w-16"></div>
                </div>
              </div>
              <div className="h-6 bg-gray-200 rounded w-12"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">最近の試合</h2>
      
      <div className="space-y-4">
        {mockMatches.map((match) => (
          <div key={match.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors duration-200">
            <div className="flex items-center space-x-4">
              <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center text-white font-bold text-sm">
                {match.champion.charAt(0)}
              </div>
              
              <div>
                <div className="font-medium text-gray-900">{match.champion}</div>
                <div className="text-sm text-gray-500">{match.date}</div>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className="text-center">
                <div className="text-sm font-medium text-gray-900">{match.kda}</div>
                <div className="text-xs text-gray-500">KDA</div>
              </div>
              
              <div className="text-center">
                <div className="text-sm font-medium text-gray-900">{match.cs}</div>
                <div className="text-xs text-gray-500">CS</div>
              </div>
              
              <div className="text-center">
                <div className="text-sm font-medium text-gray-900">{match.duration}</div>
                <div className="text-xs text-gray-500">時間</div>
              </div>
              
              <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                match.result === 'Win' 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-red-100 text-red-800'
              }`}>
                {match.result === 'Win' ? '勝利' : '敗北'}
              </div>
            </div>
          </div>
        ))}
      </div>
      
      <div className="mt-4 text-center">
        <button className="button-secondary">
          もっと見る
        </button>
      </div>
    </div>
  );
};

export default RecentMatches;