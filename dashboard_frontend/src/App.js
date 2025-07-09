import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import './App.css';
import Dashboard from './components/Dashboard';
import PlayerComparison from './components/PlayerComparison';
import PlayerDetail from './components/PlayerDetail';
import Navigation from './components/Navigation';

function App() {
  return (
    <Router>
      <div className="App min-h-screen bg-gray-50">
        <Navigation />
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/player/:playerId" element={<PlayerDetail />} />
            <Route path="/compare" element={<PlayerComparison />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;