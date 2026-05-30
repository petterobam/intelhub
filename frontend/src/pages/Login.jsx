import { useState, useEffect, useRef } from "react";
import { api } from "../api/client";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Flame } from "lucide-react";
import OAuthButtons from "../components/OAuthButtons";

// 纯 CSS 数据流动画背景
function DataStreamBG() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let raf;
    let w = (canvas.width = window.innerWidth);
    let h = (canvas.height = window.innerHeight);

    // 数据流列
    const fontSize = 14;
    const cols = Math.floor(w / fontSize);
    const drops = Array.from({ length: cols }, () => Math.random() * -100);
    // 字符集：情报相关
    const chars = "情报数据AI分析投资市场政策经济金融科技0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ{}[]<>/\\|@#$%&*+=";

    const draw = () => {
      // 半透明覆盖产生拖尾效果
      ctx.fillStyle = "rgba(2, 6, 23, 0.08)";
      ctx.fillRect(0, 0, w, h);

      for (let i = 0; i < cols; i++) {
        const char = chars[Math.floor(Math.random() * chars.length)];
        const x = i * fontSize;
        const y = drops[i] * fontSize;

        // 头部亮色，尾部渐暗
        const brightness = Math.random();
        if (brightness > 0.95) {
          ctx.fillStyle = "#f97316"; // 偶尔橙色高亮
          ctx.font = `bold ${fontSize}px monospace`;
        } else if (brightness > 0.85) {
          ctx.fillStyle = "#38bdf8"; // 偶尔天蓝
          ctx.font = `${fontSize}px monospace`;
        } else {
          ctx.fillStyle = `rgba(56, 189, 248, ${0.08 + brightness * 0.15})`;
          ctx.font = `${fontSize}px monospace`;
        }
        ctx.fillText(char, x, y);

        // 到底部后有概率重置
        if (y > h && Math.random() > 0.975) {
          drops[i] = 0;
        }
        drops[i] += 0.6 + Math.random() * 0.4;
      }
      raf = requestAnimationFrame(draw);
    };

    draw();

    const handleResize = () => {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 z-0"
      style={{ background: "linear-gradient(135deg, #020617 0%, #0f172a 50%, #020617 100%)" }}
    />
  );
}

export default function Login({ onLogin }) {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // 处理邮件链接中的 token 自动登录
  useEffect(() => {
    // OAuth 错误信息
    const oauthError = searchParams.get("oauth_error");
    if (oauthError) {
      setError(decodeURIComponent(oauthError));
      navigate("/login", { replace: true });
      return;
    }

    const token = searchParams.get("token");
    if (!token) return;

    setLoading(true);
    setError("");
    api.setToken(token);

    api.get("/api/v1/auth/me")
      .then((res) => {
        const user = res.data?.data;
        api.setUser(user);
        onLogin?.();
        const dest = user.role === "admin" ? "/" : "/plaza";
        navigate(dest, { replace: true });
      })
      .catch(() => {
        api.clearToken();
        setError("登录链接已过期，请重新登录或注册。");
      })
      .finally(() => setLoading(false));
  }, [searchParams]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    if (!email || !password) {
      setError("请输入邮箱和密码");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post("/api/v1/auth/login", { email, password });
      const { token, user } = res.data?.data || {};
      api.setToken(token);
      api.setUser(user);
      onLogin?.();
      const dest = user.role === "admin" ? "/" : "/plaza";
      navigate(dest, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!email) {
      setError("请输入邮箱地址");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post("/api/v1/auth/register", { email });
      setSuccess(res.data?.data?.message || "登录链接已发送至您的邮箱");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative overflow-hidden">
      <DataStreamBG />

      {/* 前景内容 */}
      <div className="relative z-10 min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-sm">
          {/* Logo & 标题 */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500/15 to-amber-500/5 border border-orange-500/20 mb-4">
              <Flame size={30} className="text-orange-400" />
            </div>
            <h1 className="text-3xl font-bold text-white tracking-tight">
              Intel<span className="text-blue-400">Hub</span>
            </h1>
            <p className="text-sm text-slate-500 mt-2">智能情报与投资分析平台</p>
          </div>

          {/* 登录卡片 - 毛玻璃效果 */}
          <div className="bg-[#111a2e]/70 backdrop-blur-xl rounded-2xl p-6 border border-[#1a2540]/60 shadow-2xl shadow-blue-500/5 space-y-4">
            {/* OAuth 社交登录 */}
            <OAuthButtons />

            {/* Tab 切换 */}
            <div className="flex gap-1 bg-white/[0.03] rounded-xl p-1">
              <button
                onClick={() => { setMode("login"); setError(""); setSuccess(""); }}
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  mode === "login"
                    ? "bg-blue-500/15 text-blue-400 shadow-sm shadow-blue-500/5"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                登录
              </button>
              <button
                onClick={() => { setMode("register"); setError(""); setSuccess(""); }}
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  mode === "register"
                    ? "bg-blue-500/15 text-blue-400 shadow-sm shadow-blue-500/5"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                注册
              </button>
            </div>

            {error && (
              <div className="bg-red-500/10 text-red-400 text-sm px-3 py-2 rounded-lg border border-red-500/20">
                {error}
              </div>
            )}

            {success && (
              <div className="bg-emerald-500/10 text-emerald-400 text-sm px-3 py-2 rounded-lg border border-emerald-500/20">
                {success}
              </div>
            )}

            {mode === "login" ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <label className="block text-sm text-slate-300 mb-1.5">邮箱</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="xxxxx@xxx.xxx"
                    className="w-full bg-white/[0.04] border border-[#1a2540]/80 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1.5">密码</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••"
                    className="w-full bg-white/[0.04] border border-[#1a2540]/80 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all"
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-blue-500 to-blue-600 text-white py-2.5 rounded-xl text-sm font-medium hover:from-blue-600 hover:to-blue-700 transition-all duration-200 disabled:opacity-50 shadow-lg shadow-blue-500/15"
                >
                  {loading ? "登录中..." : "登录"}
                </button>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <div>
                  <label className="block text-sm text-slate-300 mb-1.5">邮箱</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="填写邮箱，接收登录链接"
                    className="w-full bg-white/[0.04] border border-[#1a2540]/80 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all"
                  />
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">
                  注册后系统将自动订阅「生活娱乐日报」，登录链接将发送至您的邮箱。
                </p>
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-orange-500 to-orange-600 text-white py-2.5 rounded-xl text-sm font-medium hover:from-orange-600 hover:to-orange-700 transition-all disabled:opacity-50 shadow-lg shadow-orange-500/20"
                >
                  {loading ? "发送中..." : "获取登录链接"}
                </button>
              </form>
            )}
          </div>

          {/* 游客访问 */}
          <button
            onClick={() => { api.setGuest(); onLogin?.(); navigate("/plaza", { replace: true }); }}
            className="w-full mt-4 py-2.5 rounded-xl text-sm text-slate-400 border border-[#1a2540]/60 hover:text-white hover:border-[#2a3f5f]/80 transition-all duration-200 bg-transparent"
          >
            游客访问
          </button>

          <p className="text-center text-xs text-slate-600 mt-4">
            v0.1.0 · IntelHub
          </p>
        </div>
      </div>
    </div>
  );
}
