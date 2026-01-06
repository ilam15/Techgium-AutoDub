import Login from "./components/authentication/Login";
import InputPage from "./components/InputPage";
import LandingPage from "./components/LandingPage/LandingPage";
import PreviewPage from './components/PreviewPage/PreviewPage';
import Register from "./components/authentication/Register";
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
function App() {
  return (
    <>
      <Router>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/input" element={<InputPage />} />
          <Route path="/preview" element={<PreviewPage />} />
        </Routes>
      </Router>
    </>
  )
}
export default App
