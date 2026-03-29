import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { TradeHistory } from './pages/TradeHistory';
import { LearningStatus } from './pages/LearningStatus';
import { DecisionSnapshots } from './pages/DecisionSnapshots';
import { Preflight } from './pages/Preflight';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/trades" element={<TradeHistory />} />
        <Route path="/learning" element={<LearningStatus />} />
        <Route path="/decisions" element={<DecisionSnapshots />} />
        <Route path="/preflight" element={<Preflight />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
