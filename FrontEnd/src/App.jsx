import Login from "./components/authentication/Login";
import InputPage from "./components/InputPage";
import LandingPage from "./components/LandingPage/LandingPage";
import PreviewPage from './components/PreviewPage/PreviewPage';
import Register from "./components/authentication/Register";
function App() {
  return (
    <>
      <LandingPage />
      <Login />
      <Register />
      <InputPage />
      <PreviewPage />
    </>
  )
}
export default App
