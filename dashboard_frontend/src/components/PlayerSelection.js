import React from 'react';

const PlayerSelection = ({ players, selectedPlayer, onPlayerSelect }) => {
  return (
    <div className="flex flex-col space-y-2">
      <label className="text-sm font-medium text-gray-700">
        プレイヤー選択
      </label>
      <div className="flex flex-wrap gap-2">
        {players.map((player) => (
          <button
            key={player.id}
            onClick={() => onPlayerSelect(player)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-200 ${
              selectedPlayer?.id === player.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {player.name}
          </button>
        ))}
      </div>
      
      {selectedPlayer && (
        <div className="text-sm text-gray-600">
          選択中: <span className="font-medium">{selectedPlayer.name}</span>
        </div>
      )}
    </div>
  );
};

export default PlayerSelection;