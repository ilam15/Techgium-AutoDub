import axios from "axios";
import { useRef, useState } from "react";
import { toast } from "react-toastify";

const Login = () => {

  const email = useRef(null);
  const username = useRef(null);
  const password = useRef(null);


  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();

    if (!username.current.value || !email.current.value || !password.current.value) {
      toast.error("Please fill in all fields");
      return;
    } 

    if (!email.current.value.endsWith("@gmail.com")) {
      toast.error("Please enter a valid Gmail address (@gmail.com)");
      return;
    }

    setLoading(true);
    try {
      const { data } = await axios.post("https://betterknowit.onrender.com/api/users/login", {
        username: username.current.value,
        email: email.current.value,
        password: password.current.value,
      });
      console.log("response", data)
      toast.success("Login successful");
      sessionStorage.setItem("token", data.token);
      sessionStorage.setItem("user", JSON.stringify(data));
      sessionStorage.setItem("isloggedin", true);
      resetForm();
      window.location.href = "/";
    } catch (error) {
      console.error(error);
      toast.error(error.response?.data?.message || "Login failed. Please check your credentials.");
      setLoading(false);
    }
  };

  const resetForm = () => {
    email.current.value = "";
    username.current.value = "";
    password.current.value = "";
  };
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#030303]">
      <div className="w-full max-w-sm bg-[#1a1a1b] rounded-xl border border-[#343536] p-6 shadow-lg shadow-orange-500/10">

        <div className="flex justify-center mb-6">
          <div className="p-3 bg-gradient-to-br from-orange-500/20 to-orange-600/20 rounded-full">
            <svg className="w-8 h-8 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
            </svg>
          </div>
        </div>

        <h1 className="text-2xl font-bold text-center mb-6 text-white">
          Welcome Back
        </h1>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Username</label>
            <input
              type="text"
              placeholder="Enter your username"
              ref={username}
              className="w-full px-4 py-2 bg-[#272729] border border-[#343536] rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Password</label>
            <input
              type="password"
              placeholder="Enter your password"
              ref={password}
              className="w-full px-4 py-2 bg-[#272729] border border-[#343536] rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors"
            />
          </div>
          <button
            type="submit"
            onClick={handleLogin}
            disabled={loading}
            className={`w-full bg-gradient-to-r from-orange-600 to-orange-500 text-white py-2 rounded-lg font-semibold hover:from-orange-500 hover:to-orange-400 transition-all duration-300 transform hover:scale-[1.02] shadow-lg shadow-orange-500/25 ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </div>

        <p className="text-sm text-center text-gray-400 mt-6">
          Don't have an account?
          <a href="/register" className="text-orange-500 font-medium cursor-pointer hover:text-orange-400 hover:underline ml-1 transition-colors">
            Register
          </a>
        </p>
      </div>
    </div>

  )
}

export default Login