import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import DashboardPage from './pages/Dashboard/DashboardPage'
import NewInspectionPage from './pages/NewScan/NewInspectionPage'
import ProcessingPage from './pages/Processing/ProcessingPage'
import InspectionDetailsPage from './pages/Results/InspectionDetailsPage'
import HistoryPage from './pages/History/HistoryPage'
import ReportsPage from './pages/Report/ReportsPage'
import RulesPage from './pages/Rules/RulesPage'
import SettingsPage from './pages/Settings/SettingsPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/new-inspection" element={<NewInspectionPage />} />
          <Route path="/inspection/new" element={<NewInspectionPage />} />
          <Route path="/processing/:id" element={<ProcessingPage />} />
          <Route path="/results/:id" element={<InspectionDetailsPage />} />
          <Route path="/inspection/:id" element={<InspectionDetailsPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/rules" element={<RulesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
